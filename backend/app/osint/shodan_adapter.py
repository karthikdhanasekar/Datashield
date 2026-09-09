"""
DataShield OSINT - Shodan Adapter
-------------------------------------
Uses the open-source 'shodan' Python library to search for
internet-exposed devices, open ports, and services associated
with IP addresses derived from a domain or email.

What it finds:
  - Open ports / services on a target's infrastructure
  - Exposed login panels, admin interfaces
  - SSL certificate data (may contain names/emails)
  - Server banners leaking software versions

Install: pip install shodan==1.31.0
GitHub:  https://github.com/achillean/shodan-python
Docs:    https://developer.shodan.io/
API Key: Free tier available at https://account.shodan.io/

ETHICAL USE: Only queries Shodan's existing scan database.
No active port scanning is performed.
"""
import asyncio
from typing import List, Dict, Any, Optional
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


async def search_shodan_domain(domain: str) -> List[Dict[str, Any]]:
    """
    Search Shodan for infrastructure exposure related to a domain.

    Steps:
    1. Resolve domain to IP(s) via DNS
    2. Query Shodan for each IP
    3. Return findings for exposed services

    Requires SHODAN_API_KEY in .env (free tier works).
    """
    if not settings.SHODAN_API_KEY:
        logger.info("Shodan API key not configured — skipping Shodan scan")
        return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _shodan_sync, domain)


def _shodan_sync(domain: str) -> List[Dict[str, Any]]:
    """Blocking Shodan lookup — runs in thread pool."""
    try:
        import shodan
        import dns.resolver

        api = shodan.Shodan(settings.SHODAN_API_KEY)
        findings = []

        # Resolve IPs for domain
        ips = _resolve_ips(domain)
        if not ips:
            return []

        for ip in ips[:3]:  # Limit to first 3 IPs
            try:
                host = api.host(ip)
                findings.extend(_parse_shodan_host(host, domain, ip))
            except shodan.APIError as e:
                if "No information available" in str(e):
                    continue
                logger.warning("Shodan host lookup failed", ip=ip, error=str(e))
            except Exception as e:
                logger.warning("Shodan error", ip=ip, error=str(e))

        return findings

    except ImportError:
        logger.warning("shodan not installed — run: pip install shodan")
        return []
    except Exception as e:
        logger.error("Shodan scan failed", domain=domain, error=str(e))
        return []


def _resolve_ips(domain: str) -> List[str]:
    """Resolve domain to IP addresses via DNS."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "A")
        return [str(r) for r in answers]
    except Exception:
        try:
            import socket
            ip = socket.gethostbyname(domain)
            return [ip] if ip else []
        except Exception:
            return []


def _parse_shodan_host(host: Dict, domain: str, ip: str) -> List[Dict[str, Any]]:
    """Convert Shodan host data to DataShield findings."""
    findings = []
    ports = host.get("ports", [])
    vulns = host.get("vulns", {})
    hostnames = host.get("hostnames", [])
    org = host.get("org", "")
    country = host.get("country_name", "")

    # Exposed sensitive ports — higher severity
    sensitive_ports = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
        80: "HTTP", 443: "HTTPS", 3306: "MySQL", 5432: "PostgreSQL",
        6379: "Redis", 27017: "MongoDB", 9200: "Elasticsearch",
        8080: "HTTP Proxy", 8443: "HTTPS Alt", 3389: "RDP",
        445: "SMB", 139: "NetBIOS",
    }

    for port in ports:
        port_name = sensitive_ports.get(port, f"Port {port}")
        is_critical = port in (3306, 5432, 6379, 27017, 9200, 23, 3389, 445)
        severity = "critical" if is_critical else "medium"
        risk_score = 8.5 if is_critical else 4.5

        findings.append({
            "finding_type": "search_engine",
            "source_name": f"Shodan – {port_name}",
            "source_url": f"https://www.shodan.io/host/{ip}",
            "source_domain": domain,
            "source_title": f"Exposed {port_name} service on {ip}:{port}",
            "severity": severity,
            "risk_score": risk_score,
            "description": (
                f"Shodan detected an exposed {port_name} service on IP {ip} "
                f"(associated with {domain}). "
                f"Organization: {org}. Country: {country}. "
                + ("This is a high-risk database port exposure." if is_critical else "")
            ),
            "exposed_data_types": ["infrastructure", "open_port"],
            "reputation_risk": False,
            "identity_theft_risk": is_critical,
            "credential_exposure": is_critical,
            "government_id_exposure": False,
            "snippet": (
                f"IP: {ip} | Port: {port} ({port_name}) | "
                f"Org: {org} | Country: {country} | "
                f"Hostnames: {', '.join(hostnames[:3])}"
            ),
            "raw_data": {
                "ip": ip,
                "port": port,
                "service": port_name,
                "org": org,
                "country": country,
                "hostnames": hostnames,
                "shodan_url": f"https://www.shodan.io/host/{ip}",
            },
        })

    # Known CVEs (vulnerabilities)
    for cve_id, cve_data in list(vulns.items())[:5]:
        findings.append({
            "finding_type": "search_engine",
            "source_name": f"Shodan – CVE",
            "source_url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            "source_domain": domain,
            "source_title": f"Known vulnerability: {cve_id}",
            "severity": "critical",
            "risk_score": 9.5,
            "description": (
                f"Shodan identified vulnerability {cve_id} on IP {ip} "
                f"associated with {domain}. "
                f"CVSS: {cve_data.get('cvss', 'N/A')}. "
                "This indicates the server may be running vulnerable software."
            ),
            "exposed_data_types": ["vulnerability", "infrastructure"],
            "reputation_risk": True,
            "identity_theft_risk": True,
            "credential_exposure": True,
            "government_id_exposure": False,
            "snippet": f"CVE: {cve_id} | CVSS: {cve_data.get('cvss', 'N/A')} | IP: {ip}",
            "raw_data": {"cve": cve_id, "ip": ip, "domain": domain, **cve_data},
        })

    return findings
