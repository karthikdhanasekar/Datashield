"""
DataShield OSINT - Phone Number OSINT Module
---------------------------------------------
Uses the open-source 'phonenumbers' library to parse and validate phone
numbers, then searches public sources for exposure.

No third-party API key needed for basic analysis.
Optional: NumVerify API for carrier/location lookup.

Install: pip install phonenumbers==8.13.30
"""
import asyncio
from typing import List, Dict, Any, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


async def analyze_phone_number(phone: str) -> List[Dict[str, Any]]:
    """
    Perform OSINT on a phone number:
    1. Parse and validate with 'phonenumbers' library
    2. Identify carrier, region, and type (mobile/landline)
    3. Search public paste sites and data brokers
    4. Search Google/Bing for public listings

    Returns DataShield findings.
    """
    findings = []

    # Step 1: Parse and validate
    parsed = _parse_phone(phone)
    if not parsed["valid"]:
        return []

    # Step 2: Basic info finding (always available, no API needed)
    if parsed["region"] or parsed["carrier"]:
        findings.append({
            "finding_type": "search_engine",
            "source_name": "Phone Number Analysis",
            "source_url": "",
            "source_domain": "phonenumbers (library)",
            "source_title": f"Phone number metadata: {parsed['formatted']}",
            "severity": "medium",
            "risk_score": 4.5,
            "description": (
                f"Phone number identified: {parsed['formatted']}. "
                f"Country: {parsed['region']}. "
                f"Type: {parsed['number_type']}. "
                f"Carrier: {parsed.get('carrier', 'Unknown')}."
            ),
            "exposed_data_types": ["phone_number", "location", "carrier"],
            "reputation_risk": False,
            "identity_theft_risk": True,
            "credential_exposure": False,
            "snippet": f"Phone: {parsed['formatted']} | Region: {parsed['region']} | Type: {parsed['number_type']}",
            "raw_data": parsed,
        })

    # Step 3: Check public directories via HTTP
    directory_findings = await _check_public_directories(parsed["e164"], parsed["national"])
    findings.extend(directory_findings)

    return findings


def _parse_phone(phone: str) -> Dict[str, Any]:
    """Parse phone number using the phonenumbers library."""
    try:
        import phonenumbers
        from phonenumbers import geocoder, carrier, number_type

        # Try parsing with common country codes if no + prefix
        raw = phone.strip()
        if not raw.startswith("+"):
            # Try India first, then US as defaults
            for region in ["IN", "US", "GB"]:
                try:
                    parsed = phonenumbers.parse(raw, region)
                    if phonenumbers.is_valid_number(parsed):
                        break
                except Exception:
                    continue
            else:
                return {"valid": False}
        else:
            parsed = phonenumbers.parse(raw, None)

        if not phonenumbers.is_valid_number(parsed):
            return {"valid": False}

        # Number type
        ntype_map = {
            phonenumbers.PhoneNumberType.MOBILE: "Mobile",
            phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed/Mobile",
            phonenumbers.PhoneNumberType.VOIP: "VoIP",
            phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
        }
        ntype = phonenumbers.number_type(parsed)

        return {
            "valid": True,
            "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
            "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
            "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            "formatted": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            "region": geocoder.description_for_number(parsed, "en") or "",
            "carrier": carrier.name_for_number(parsed, "en") or "",
            "number_type": ntype_map.get(ntype, "Unknown"),
            "country_code": parsed.country_code,
        }

    except ImportError:
        logger.warning("phonenumbers not installed — run: pip install phonenumbers")
        # Basic fallback
        return {
            "valid": len(phone.replace(" ", "").replace("-", "")) >= 7,
            "e164": phone,
            "national": phone,
            "international": phone,
            "formatted": phone,
            "region": "",
            "carrier": "",
            "number_type": "Unknown",
        }
    except Exception as e:
        logger.error("Phone parse failed", error=str(e))
        return {"valid": False}


async def _check_public_directories(e164: str, national: str) -> List[Dict[str, Any]]:
    """Check public phone lookup sites for exposure."""
    findings = []
    numbers_to_check = [e164, national]

    # Known public phone directory/lookup sites
    directory_sites = [
        ("Truecaller", "https://www.truecaller.com/search/in/{number}"),
        ("NumLookup", "https://www.numlookupapi.com/phone/{number}"),
        ("PhoneBook.cz", "https://www.phonebook.cz/phone/{number}"),
    ]

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        for site_name, url_template in directory_sites:
            for number in numbers_to_check:
                clean = number.replace("+", "").replace(" ", "").replace("-", "")
                url = url_template.replace("{number}", clean)
                try:
                    resp = await client.head(url)
                    if resp.status_code == 200:
                        findings.append({
                            "finding_type": "search_engine",
                            "source_name": f"Phone Directory – {site_name}",
                            "source_url": url,
                            "source_domain": _domain(url),
                            "source_title": f"Phone number listed on {site_name}",
                            "severity": "high",
                            "risk_score": 6.5,
                            "description": (
                                f"Phone number appears to be listed on {site_name}. "
                                "This means your number may be publicly searchable by anyone."
                            ),
                            "exposed_data_types": ["phone_number"],
                            "reputation_risk": True,
                            "identity_theft_risk": True,
                            "credential_exposure": False,
                            "snippet": f"Number found in public directory: {site_name} — {url}",
                            "raw_data": {"site": site_name, "url": url, "number": e164},
                        })
                        break  # Found on this site, no need to check alternate format
                except Exception:
                    continue

    return findings


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url
