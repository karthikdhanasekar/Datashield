"""
DataShield OSINT - Takedown Service
Generates removal request emails and discovers website contacts
"""
import asyncio
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import httpx
import whois as pythonwhois


def generate_takedown_email(
    template_type,
    finding,
    user,
    custom_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a takedown email from a template."""
    templates = {
        "privacy_removal": _privacy_removal_template,
        "gdpr_removal": _gdpr_removal_template,
        "right_to_be_forgotten": _rtbf_template,
        "dmca_personal_data": _dmca_template,
    }

    template_fn = templates.get(str(template_type).replace("TakedownTemplateType.", "").lower())
    if not template_fn:
        template_fn = _privacy_removal_template

    result = template_fn(finding, user)
    if custom_message:
        result["body"] += f"\n\nAdditional information:\n{custom_message}"
    return result


def _privacy_removal_template(finding, user) -> Dict:
    name = user.full_name or user.email
    domain = finding.source_domain or "your website"
    url = finding.source_url or ""
    return {
        "subject": f"Privacy Data Removal Request — {domain}",
        "body": f"""Dear Privacy Officer / Website Administrator,

I am writing to formally request the removal of my personal information from your platform.

I have identified the following URL containing my personal data:
URL: {url}

My information appears to be publicly accessible without my consent and in violation of applicable privacy laws.

As the data subject, I hereby request that you:
1. Remove the above-listed personal data immediately
2. Cease all processing of my personal information
3. Confirm in writing that the data has been deleted

Please confirm receipt of this request and the expected timeline for removal.

Regards,
{name}
""",
        "legal_references": [
            "General Data Protection Regulation (GDPR) — Art. 17 Right to Erasure",
            "Information Technology Act, 2000 (India) — Section 43A",
        ],
    }


def _gdpr_removal_template(finding, user) -> Dict:
    name = user.full_name or user.email
    email = user.email
    domain = finding.source_domain or "your website"
    url = finding.source_url or ""
    return {
        "subject": f"GDPR Data Subject Request — Right to Erasure — {domain}",
        "body": f"""Dear Data Protection Officer,

I am exercising my rights under the General Data Protection Regulation (GDPR), specifically Article 17 — Right to Erasure ('Right to Be Forgotten').

Data Subject: {name}
Contact: {email}

I have identified my personal data at the following location:
URL: {url}

Grounds for erasure:
- The data is no longer necessary for the purposes for which it was collected
- I withdraw consent for processing
- The data has been unlawfully processed

Under GDPR Article 12, you are required to respond within one calendar month.

Please confirm:
1. The deletion of my personal data
2. Any third parties to whom my data has been disclosed
3. The date of completion of the erasure

Yours faithfully,
{name}
{email}
""",
        "legal_references": [
            "GDPR Article 17 — Right to Erasure",
            "GDPR Article 12 — Transparent information and communication",
            "GDPR Article 19 — Notification obligation regarding rectification or erasure",
        ],
    }


def _rtbf_template(finding, user) -> Dict:
    name = user.full_name or user.email
    domain = finding.source_domain or "your website"
    url = finding.source_url or ""
    return {
        "subject": f"Right to Be Forgotten Request — {domain}",
        "body": f"""To Whom It May Concern,

I am formally invoking my Right to Be Forgotten as recognised under international privacy frameworks.

I request the immediate de-indexing and removal of the following content containing my personal information:
URL: {url}

This request is made on the grounds that the continued availability of this data:
- Infringes on my fundamental right to privacy
- May cause harm to my reputation and personal safety
- Was published without my explicit consent

I expect a response within 30 days confirming the removal.

Regards,
{name}
""",
        "legal_references": [
            "European Court of Justice — Google Spain v AEPD (Right to Be Forgotten)",
            "GDPR Article 17",
            "UK GDPR Section 47",
        ],
    }


def _dmca_template(finding, user) -> Dict:
    name = user.full_name or user.email
    email = user.email
    domain = finding.source_domain or "your website"
    url = finding.source_url or ""
    return {
        "subject": f"Personal Data Removal Request — {domain}",
        "body": f"""Dear Abuse / Privacy Department,

I am writing to request the removal of personally identifiable information published on your platform without authorisation.

Affected URL: {url}

The content identified at the above URL contains my personal information including but not limited to identifying details that were published without my consent and constitute a privacy violation.

I request:
1. Immediate removal of the content
2. Prevention of re-publication
3. Written confirmation of removal

Contact for correspondence:
Name: {name}
Email: {email}

Sincerely,
{name}
""",
        "legal_references": [
            "Privacy Act 1988 (Australia)",
            "Personal Data Protection Act (PDPA)",
            "California Consumer Privacy Act (CCPA) — Section 1798.105",
        ],
    }


async def discover_website_contacts(domain: str) -> Dict[str, Optional[str]]:
    """
    Discover contact emails for a domain using WHOIS and common endpoints.
    Returns ranked contact options.
    """
    contacts = {
        "contact_email": None,
        "abuse_email": None,
        "privacy_officer_email": None,
        "contact_form_url": None,
        "whois_registrar": None,
    }

    if not domain:
        return contacts

    # Try WHOIS lookup
    try:
        w = pythonwhois.query(domain)
        if w:
            emails = w.get("emails", [])
            if emails:
                contacts["contact_email"] = emails[0] if isinstance(emails, list) else emails
            contacts["whois_registrar"] = w.get("registrar", [None])[0] if w.get("registrar") else None
    except Exception:
        pass

    # Common abuse/privacy emails
    if not contacts["abuse_email"]:
        contacts["abuse_email"] = f"abuse@{domain}"
    if not contacts["privacy_officer_email"]:
        contacts["privacy_officer_email"] = f"privacy@{domain}"

    # Check common contact form paths
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        for path in ["/contact", "/privacy", "/dmca", "/abuse"]:
            try:
                url = f"https://{domain}{path}"
                resp = await client.head(url)
                if resp.status_code < 400:
                    contacts["contact_form_url"] = url
                    break
            except Exception:
                continue

    return contacts
