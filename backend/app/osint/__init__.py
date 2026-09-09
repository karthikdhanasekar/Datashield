"""
DataShield OSINT Engine
========================
Open-source OSINT tool integrations for digital footprint discovery.

Tools integrated:
  holehe          — Email registration check on 120+ sites (pip install holehe)
  maigret         — Username OSINT across 3000+ sites (pip install maigret)
  theHarvester    — Email/subdomain harvesting (pip install theHarvester)
  shodan          — Internet-exposed infrastructure (pip install shodan)
  HIBP            — HaveIBeenPwned breach API
  phonenumbers    — Phone number parsing & validation
  pastebin_scraper— Public paste site search
  search_engine   — Google Custom Search + Bing
  social_media    — GitHub, Reddit, Twitter public profiles
  document_scanner— Public PDF/Doc/Spreadsheet search
  exposure_classifier — Severity scoring engine
"""

from app.osint.osint_engine import run_full_osint
from app.osint.exposure_classifier import ExposureClassifier
from app.osint.breach_monitor import BreachMonitor
from app.osint.holehe_adapter import check_email_registrations
from app.osint.maigret_adapter import check_username_maigret
from app.osint.theharvester_adapter import harvest_domain
from app.osint.shodan_adapter import search_shodan_domain
from app.osint.pastebin_scraper import search_pastes
from app.osint.phone_osint import analyze_phone_number
from app.osint.search_engine import SearchEngineScanner
from app.osint.social_media import SocialMediaScanner
from app.osint.document_scanner import DocumentScanner

__all__ = [
    "run_full_osint",
    "ExposureClassifier",
    "BreachMonitor",
    "check_email_registrations",
    "check_username_maigret",
    "harvest_domain",
    "search_shodan_domain",
    "search_pastes",
    "analyze_phone_number",
    "SearchEngineScanner",
    "SocialMediaScanner",
    "DocumentScanner",
]
