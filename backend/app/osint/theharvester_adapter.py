"""
DataShield OSINT - theHarvester Adapter
-------------------------------------
Wraps the open-source 'theHarvester' tool to find emails, subdomains,
hostnames, and employee names associated with a target domain.

theHarvester searches: Google, Bing, DuckDuckGo, LinkedIn, Shodan,
                       Hunter.io, VirusTotal, and many more.

Install: pip install theHarvester==4.5.2
GitHub:  https://github.com/laramies/theHarvester
License: GNU GPLv2
"""
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)

# theHarvester data sources to use (no API key required for these)
FREE_SOURCES = ["bing", "duckduckgo", "dnsdumpster", "urlscan", "crtsh"]
# Sources that need API keys (optional, used if configured)
PAID_SOURCES = ["google", "linkedin", "hunter", "shodan"]


async def harvest_domain(
    domain: str,
    limit: int = 200,
    use_paid_sources: bool = False,
) -> List[Dict[str, Any]]:
    """
    Run theHarvester on a domain and return DataShield findings.

    Discovers:
    - Email addresses associated with the domain
    - Subdomains / hosts
    - Employee/person names

    Args:
        domain:            Target domain (e.g. "example.com")
        limit:             Max results per source
        use_paid_sources:  Include paid API sources (Google, LinkedIn, etc.)

    Returns:
        List of DataShield finding dicts.
    """
    if not domain or "." not in domain:
        return []

    # Strip protocol/path — theHarvester wants bare domain
    domain = _clean_domain(domain)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _run_harvester_sync, domain, limit, use_paid_sources
    )


def _run_harvester_sync(
    domain: str, limit: int, use_paid_sources: bool
) -> List[Dict[str, Any]]:
    """Blocking implementation — runs in thread pool."""
    sources = FREE_SOURCES[:]
    if use_paid_sources:
        sources.extend(PAID_SOURCES)

    sources_str = ",".join(sources)

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "harvest.json"

        cmd = [
            sys.executable, "-m", "theHarvester",
            "-d", domain,
            "-l", str(limit),
            "-b", sources_str,
            "-f", str(json_path).replace(".json", ""),  # theHarvester adds extension
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=tmpdir,
            )

            # theHarvester saves output as <name>.json
            actual_json = Path(tmpdir) / f"{json_path.stem}.json"
            if not actual_json.exists():
                # Try without path stem variation
                candidates = list(Path(tmpdir).glob("*.json"))
                if candidates:
                    actual_json = candidates[0]
                else:
                    logger.warning("theHarvester produced no JSON output")
                    return _parse_stdout_fallback(result.stdout, domain)

            raw = json.loads(actual_json.read_text(encoding="utf-8"))
            return _parse_harvester_json(raw, domain)

        except subprocess.TimeoutExpired:
            logger.warning("theHarvester timed out", domain=domain)
            return []
        except FileNotFoundError:
            logger.warning("theHarvester not installed — run: pip install theHarvester")
            return _demo_results(domain)
        except Exception as e:
            logger.error("theHarvester failed", error=str(e), domain=domain)
            return _demo_results(domain)


def _parse_harvester_json(raw: Dict, domain: str) -> List[Dict[str, Any]]:
    """
    Parse theHarvester JSON output.

    theHarvester JSON structure:
    {
      "emails": ["user@domain.com", ...],
      "hosts": ["sub.domain.com", ...],
      "people": ["John Doe", ...],
      "interesting_urls": [...]
    }
    """
    findings = []

    # ── Email addresses found ─────────────────────────────────────────────────
    emails = raw.get("emails", [])
    for email in emails:
        if "@" not in email:
            continue
        findings.append({
            "finding_type": "search_engine",
            "source_name": "theHarvester – Email Discovery",
            "source_url": f"https://{domain}",
            "source_domain": domain,
            "source_title": f"Email address exposed: {email}",
            "severity": "high",
            "risk_score": 7.0,
            "description": (
                f"Email address '{email}' was found publicly associated with "
                f"the domain '{domain}' via search engine harvesting. "
                "This email could be targeted for phishing or spam."
            ),
            "exposed_data_types": ["email", "corporate_identity"],
            "reputation_risk": True,
            "identity_theft_risk": True,
            "credential_exposure": False,
            "snippet": f"Email harvested from public sources: {email}",
            "raw_data": {"email": email, "domain": domain, "source": "theHarvester"},
        })

    # ── Subdomains / hosts ────────────────────────────────────────────────────
    hosts = raw.get("hosts", [])
    for host in hosts[:20]:   # Cap at 20 to avoid noise
        findings.append({
            "finding_type": "search_engine",
            "source_name": "theHarvester – Subdomain Discovery",
            "source_url": f"https://{host}",
            "source_domain": host,
            "source_title": f"Public subdomain found: {host}",
            "severity": "low",
            "risk_score": 2.0,
            "description": (
                f"Subdomain '{host}' is publicly indexed for domain '{domain}'. "
                "Exposed subdomains can indicate infrastructure layout."
            ),
            "exposed_data_types": ["subdomain", "infrastructure"],
            "reputation_risk": False,
            "identity_theft_risk": False,
            "credential_exposure": False,
            "snippet": f"Subdomain found: {host}",
            "raw_data": {"host": host, "domain": domain, "source": "theHarvester"},
        })

    # ── People / employee names ───────────────────────────────────────────────
    people = raw.get("people", [])
    for person in people:
        findings.append({
            "finding_type": "search_engine",
            "source_name": "theHarvester – Person Discovery",
            "source_url": f"https://{domain}",
            "source_domain": domain,
            "source_title": f"Person name found: {person}",
            "severity": "medium",
            "risk_score": 4.5,
            "description": (
                f"Person name '{person}' was found publicly associated with "
                f"domain '{domain}'. This may be an employee or contact."
            ),
            "exposed_data_types": ["full_name", "employee_info"],
            "reputation_risk": True,
            "identity_theft_risk": True,
            "credential_exposure": False,
            "snippet": f"Name found via OSINT harvesting: {person}",
            "raw_data": {"name": person, "domain": domain, "source": "theHarvester"},
        })

    logger.info(
        "theHarvester complete",
        domain=domain,
        emails=len(emails),
        hosts=len(hosts),
        people=len(people),
    )
    return findings


def _parse_stdout_fallback(stdout: str, domain: str) -> List[Dict[str, Any]]:
    """Parse plain text output from theHarvester if JSON fails."""
    import re
    findings = []
    emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", stdout)
    for email in set(emails):
        if domain.lower() in email.lower():
            findings.append({
                "finding_type": "search_engine",
                "source_name": "theHarvester – Email",
                "source_url": f"https://{domain}",
                "source_domain": domain,
                "source_title": f"Email found: {email}",
                "severity": "high",
                "risk_score": 7.0,
                "description": f"Email '{email}' found via search engine harvesting.",
                "exposed_data_types": ["email"],
                "reputation_risk": True,
                "identity_theft_risk": True,
                "credential_exposure": False,
                "snippet": f"Harvested email: {email}",
                "raw_data": {"email": email, "source": "theHarvester-stdout"},
            })
    return findings


def _clean_domain(domain: str) -> str:
    """Strip protocol and path from a domain string."""
    domain = domain.strip().lower()
    if domain.startswith(("http://", "https://")):
        domain = urlparse(domain).netloc
    return domain.split("/")[0]


def _demo_results(domain: str) -> List[Dict[str, Any]]:
    """Demo results when theHarvester is not installed."""
    return [
        {
            "finding_type": "search_engine",
            "source_name": "theHarvester (demo)",
            "source_url": f"https://{domain}",
            "source_domain": domain,
            "source_title": f"Email/subdomain discovery for {domain}",
            "severity": "medium",
            "risk_score": 4.0,
            "description": (
                "Demo result: theHarvester not installed. "
                "Install with: pip install theHarvester"
            ),
            "exposed_data_types": ["email", "subdomain"],
            "reputation_risk": True,
            "identity_theft_risk": False,
            "credential_exposure": False,
            "snippet": "Demo mode — install theHarvester for real email/subdomain harvesting",
            "raw_data": {"demo": True},
        }
    ]
