"""
DataShield OSINT - OSINT Module Tests
Tests for all OSINT tool adapters (mocked external calls)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.osint.exposure_classifier import ExposureClassifier
from app.osint.breach_monitor import BreachMonitor
from app.osint.search_engine import SearchEngineScanner
from app.osint.pastebin_scraper import _infer_data_types, _has_credentials


# ── ExposureClassifier ────────────────────────────────────────────────────────

class TestExposureClassifier:
    def setup_method(self):
        self.clf = ExposureClassifier()

    def test_breach_with_password_is_critical(self):
        finding = {
            "finding_type": "breach",
            "exposed_data_types": ["passwords", "email_addresses"],
        }
        result = self.clf.classify(finding)
        assert result.severity == "critical"
        assert result.risk_score >= 8.0
        assert result.risk_factors["credential_exposure"] is True

    def test_social_media_low_severity(self):
        finding = {
            "finding_type": "social_media",
            "exposed_data_types": ["username"],
        }
        result = self.clf.classify(finding)
        assert result.severity in ("low", "medium")
        assert result.risk_factors["reputation_risk"] is True

    def test_government_id_exposure_is_critical(self):
        finding = {
            "finding_type": "search_engine",
            "exposed_data_types": ["aadhaar", "email"],
        }
        result = self.clf.classify(finding)
        assert result.severity == "critical"
        assert result.risk_factors["government_id_exposure"] is True

    def test_paste_site_is_high(self):
        finding = {
            "finding_type": "paste_site",
            "exposed_data_types": ["email"],
        }
        result = self.clf.classify(finding)
        assert result.risk_score >= 7.0

    def test_overall_exposure_score_empty(self):
        score = self.clf.calculate_overall_exposure_score([])
        assert score == 0.0

    def test_overall_exposure_score_capped_at_100(self):
        findings = [
            {"finding_type": "breach", "severity": "critical", "is_removed": False, "is_false_positive": False}
            for _ in range(10)
        ]
        score = self.clf.calculate_overall_exposure_score(findings)
        assert score <= 100.0

    def test_false_positives_excluded(self):
        findings = [
            {"finding_type": "breach", "severity": "critical", "is_false_positive": True, "is_removed": False},
        ]
        score = self.clf.calculate_overall_exposure_score(findings)
        assert score == 0.0

    def test_removed_findings_excluded(self):
        findings = [
            {"finding_type": "breach", "severity": "critical", "is_false_positive": False, "is_removed": True},
        ]
        score = self.clf.calculate_overall_exposure_score(findings)
        assert score == 0.0


# ── BreachMonitor ─────────────────────────────────────────────────────────────

class TestBreachMonitor:
    def setup_method(self):
        self.monitor = BreachMonitor()

    def test_classify_breach_with_passwords_is_critical(self):
        breach = {"DataClasses": ["Passwords", "Email addresses"]}
        assert self.monitor.classify_breach_severity(breach) == "critical"

    def test_classify_breach_with_phone_is_high(self):
        breach = {"DataClasses": ["Phone numbers", "Dates of birth"]}
        assert self.monitor.classify_breach_severity(breach) == "high"

    def test_classify_breach_email_only_is_medium(self):
        breach = {"DataClasses": ["Email addresses", "Usernames"]}
        assert self.monitor.classify_breach_severity(breach) == "medium"

    def test_format_findings_returns_list(self):
        breaches = [
            {
                "Name": "TestBreach",
                "Title": "Test Breach",
                "Domain": "test.com",
                "BreachDate": "2023-01-01",
                "PwnCount": 500000,
                "DataClasses": ["Passwords", "Email addresses"],
                "IsVerified": True,
            }
        ]
        findings = self.monitor.format_findings(breaches, "test@test.com")
        assert len(findings) == 1
        assert findings[0]["finding_type"] == "breach"
        assert findings[0]["severity"] == "critical"
        assert findings[0]["credential_exposure"] is True

    def test_format_findings_empty_list(self):
        assert self.monitor.format_findings([], "test@test.com") == []

    def test_mock_breach_check_returns_empty_list(self):
        """
        _mock_breach_check is now a no-op — XposedOrNot provides real free data.
        It should return an empty list (not demo data).
        """
        monitor = BreachMonitor()
        result = monitor._mock_breach_check("demo@test.com")
        assert isinstance(result, list)
        assert result == []

    def test_known_breach_lookup_table_populated(self):
        """The known-breach table should have entries for major breaches."""
        from app.osint.breach_monitor import _KNOWN_BREACH_DATA
        assert "Adobe" in _KNOWN_BREACH_DATA
        assert "LinkedIn" in _KNOWN_BREACH_DATA
        assert "Passwords" in _KNOWN_BREACH_DATA["Adobe"]["classes"]

    @pytest.mark.asyncio
    async def test_password_pwned_returns_int(self):
        """k-Anonymity password check should return 0 for strong unique password."""
        # Use a long random string that is almost certainly not in breach DB
        count = await self.monitor.check_password_pwned("Xk9#mQ2!vPzL7@nW3$rYqA")
        assert isinstance(count, int)
        assert count >= 0


# ── SearchEngineScanner ───────────────────────────────────────────────────────

class TestSearchEngineScanner:
    def setup_method(self):
        self.scanner = SearchEngineScanner()

    def test_build_queries_email(self):
        queries = self.scanner.build_queries("test@example.com", "email")
        assert len(queries) >= 2
        assert any("test@example.com" in q for q in queries)

    def test_build_queries_username(self):
        queries = self.scanner.build_queries("johndoe", "username")
        assert len(queries) >= 1
        assert any("johndoe" in q for q in queries)

    def test_filter_skips_safe_domains(self):
        results = [
            {"link": "https://google.com/search?q=test", "title": "Google", "snippet": "test@example.com"},
            {"link": "https://pastebin.com/abc123", "title": "Paste", "snippet": "test@example.com leaked"},
        ]
        findings = self.scanner.filter_and_classify(results, "test@example.com")
        domains = [f["source_domain"] for f in findings]
        assert "google.com" not in domains

    def test_filter_only_includes_matching_results(self):
        results = [
            {"link": "https://example.com/page", "title": "Page", "snippet": "no match here"},
        ]
        findings = self.scanner.filter_and_classify(results, "specific_query_xyz")
        assert len(findings) == 0

    def test_classify_pastebin_is_critical(self):
        severity, score = self.scanner._classify_result("pastebin.com", "Leaked data", "password dump")
        assert severity == "critical"
        assert score >= 8.0

    def test_classify_people_search_is_high(self):
        severity, score = self.scanner._classify_result("whitepages.com", "Profile", "address phone")
        assert severity == "high"

    def test_classify_generic_is_medium(self):
        severity, score = self.scanner._classify_result("somewebsite.com", "Article", "general content")
        assert severity == "medium"


# ── Pastebin Scraper Helpers ──────────────────────────────────────────────────

class TestPastebinHelpers:
    def test_infer_data_types_email(self):
        types = _infer_data_types("user@example.com was found here")
        assert "email" in types

    def test_infer_data_types_password(self):
        types = _infer_data_types("password: secret123")
        assert "password" in types

    def test_infer_data_types_phone(self):
        types = _infer_data_types("mobile: 9876543210")
        assert "phone_number" in types

    def test_infer_data_types_default(self):
        types = _infer_data_types("some random text with no personal info")
        assert "personal_info" in types

    def test_has_credentials_detects_password(self):
        assert _has_credentials("username: admin\npassword: secret") is True

    def test_has_credentials_false_for_clean(self):
        assert _has_credentials("this is a normal article about privacy") is False


# ── OSINT Engine routing ──────────────────────────────────────────────────────

class TestOSINTEngineRouting:
    """Test that the engine routes to the correct modules for each scan type."""

    def test_email_scan_builds_tasks(self):
        from app.osint.osint_engine import _build_task_list
        tasks = _build_task_list("test@example.com", "email", ["breach", "search_engine"])
        names = [t[0] for t in tasks]
        assert any("HIBP" in n or "Breach" in n for n in names)
        assert any("Search" in n for n in names)

    def test_username_scan_builds_maigret(self):
        from app.osint.osint_engine import _build_task_list
        tasks = _build_task_list("johndoe", "username", ["maigret", "social_media"])
        names = [t[0] for t in tasks]
        assert any("Maigret" in n or "maigret" in n.lower() for n in names)

    def test_phone_scan_routes_to_phone_module(self):
        from app.osint.osint_engine import _build_task_list
        tasks = _build_task_list("+919876543210", "phone", ["phone"])
        names = [t[0] for t in tasks]
        assert any("Phone" in n for n in names)

    def test_government_id_scan_uses_search(self):
        from app.osint.osint_engine import _build_task_list
        tasks = _build_task_list("ABCDE1234F", "pan", ["search_engine", "paste"])
        assert len(tasks) >= 1

    def test_deduplication_removes_same_url(self):
        from app.osint.osint_engine import _deduplicate
        findings = [
            {"source_url": "https://example.com", "risk_score": 5.0},
            {"source_url": "https://example.com", "risk_score": 8.0},  # higher score wins
            {"source_url": "https://other.com",   "risk_score": 3.0},
        ]
        deduped = _deduplicate(findings)
        urls = [f["source_url"] for f in deduped]
        assert urls.count("https://example.com") == 1
        # The higher risk score entry should be kept
        kept = next(f for f in deduped if f["source_url"] == "https://example.com")
        assert kept["risk_score"] == 8.0
