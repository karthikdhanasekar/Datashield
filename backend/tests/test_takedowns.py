"""
DataShield OSINT - Takedown & Security Tests
"""
import pytest
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, generate_totp_secret,
    verify_totp, get_totp_uri, generate_qr_code, hash_evidence,
    generate_secure_token, has_permission
)
from app.services.takedown_service import generate_takedown_email


# ── Security utilities ────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_and_verify(self):
        pwd = "MySecret@123"
        hashed = hash_password(pwd)
        assert hashed != pwd
        assert verify_password(pwd, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_is_different_each_time(self):
        """bcrypt uses random salt — same input produces different hashes."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2


class TestJWT:
    def test_access_token_decode(self):
        token = create_access_token("user-123", role="individual")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "individual"
        assert payload["type"] == "access"

    def test_refresh_token_decode(self):
        token = create_refresh_token("user-456")
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_token_has_jti(self):
        token = create_access_token("user-789")
        payload = decode_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) > 0

    def test_invalid_token_raises(self):
        from jose import JWTError
        with pytest.raises(JWTError):
            decode_token("invalid.token.here")


class TestMFA:
    def test_totp_generates_valid_secret(self):
        secret = generate_totp_secret()
        assert len(secret) == 32
        assert secret.isalpha() or secret.isalnum()

    def test_totp_verify_correct_code(self):
        import pyotp
        secret = generate_totp_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_totp_verify_wrong_code(self):
        secret = generate_totp_secret()
        assert verify_totp(secret, "000000") is False

    def test_qr_code_returns_base64(self):
        secret = generate_totp_secret()
        uri = get_totp_uri(secret, "test@example.com")
        qr = generate_qr_code(uri)
        assert isinstance(qr, str)
        assert len(qr) > 100  # valid base64 PNG


class TestRBAC:
    def test_individual_cannot_access_admin(self):
        assert has_permission("individual", "admin") is False

    def test_admin_can_access_all(self):
        assert has_permission("admin", "admin") is True
        assert has_permission("admin", "organization") is True
        assert has_permission("admin", "individual") is True

    def test_organization_cannot_access_admin(self):
        assert has_permission("organization", "admin") is False

    def test_organization_can_access_individual(self):
        assert has_permission("organization", "individual") is True


class TestEvidenceHashing:
    def test_hash_produces_hex_string(self):
        h = hash_evidence(b"test content")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_content_same_hash(self):
        content = b"consistent content"
        assert hash_evidence(content) == hash_evidence(content)

    def test_different_content_different_hash(self):
        assert hash_evidence(b"content A") != hash_evidence(b"content B")


class TestSecureToken:
    def test_token_minimum_length(self):
        token = generate_secure_token(32)
        assert len(token) >= 32

    def test_tokens_are_unique(self):
        t1 = generate_secure_token()
        t2 = generate_secure_token()
        assert t1 != t2


# ── Takedown email generation ─────────────────────────────────────────────────

class MockFinding:
    source_url = "https://example.com/leaked"
    source_domain = "example.com"
    exposed_data_types = ["email", "phone"]


class MockUser:
    email = "victim@example.com"
    full_name = "Test User"


class TestTakedownTemplates:
    def _make_finding(self):
        return MockFinding()

    def _make_user(self):
        return MockUser()

    def test_gdpr_template_has_legal_refs(self):
        from app.models.takedown import TakedownTemplateType
        result = generate_takedown_email(
            TakedownTemplateType.GDPR_REMOVAL,
            self._make_finding(),
            self._make_user(),
        )
        assert "subject" in result
        assert "body" in result
        assert "legal_references" in result
        assert len(result["legal_references"]) >= 1
        assert "GDPR" in result["body"] or "GDPR" in " ".join(result["legal_references"])

    def test_privacy_template_contains_url(self):
        from app.models.takedown import TakedownTemplateType
        result = generate_takedown_email(
            TakedownTemplateType.PRIVACY_REMOVAL,
            self._make_finding(),
            self._make_user(),
        )
        assert "example.com" in result["body"]

    def test_rtbf_template_generated(self):
        from app.models.takedown import TakedownTemplateType
        result = generate_takedown_email(
            TakedownTemplateType.RIGHT_TO_BE_FORGOTTEN,
            self._make_finding(),
            self._make_user(),
        )
        assert len(result["body"]) > 100

    def test_custom_message_appended(self):
        from app.models.takedown import TakedownTemplateType
        result = generate_takedown_email(
            TakedownTemplateType.PRIVACY_REMOVAL,
            self._make_finding(),
            self._make_user(),
            custom_message="Please respond within 7 days.",
        )
        assert "Please respond within 7 days." in result["body"]

    def test_all_templates_have_subject(self):
        from app.models.takedown import TakedownTemplateType
        for ttype in TakedownTemplateType:
            result = generate_takedown_email(ttype, self._make_finding(), self._make_user())
            assert result["subject"]
            assert len(result["subject"]) > 5
