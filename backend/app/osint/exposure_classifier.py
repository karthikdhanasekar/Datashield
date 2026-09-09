"""
DataShield OSINT - Exposure Classification Engine
Classifies finding severity and calculates risk scores
"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ExposureClassification:
    severity: str       # low | medium | high | critical
    risk_score: float   # 0.0 - 10.0
    risk_factors: Dict[str, bool]
    reasoning: str


class ExposureClassifier:
    """
    Classifies the severity of personal data exposures using
    a multi-factor risk scoring model.
    """

    # Base scores by finding type
    BASE_SCORES = {
        "breach": 7.0,
        "social_media": 3.5,
        "search_engine": 4.5,
        "document": 6.0,
        "paste_site": 8.0,
        "forum": 3.0,
        "news": 2.5,
    }

    # Data type risk weights
    DATA_TYPE_WEIGHTS = {
        "passwords": 3.0,
        "credit_cards": 3.0,
        "bank_account_numbers": 3.0,
        "ssn": 3.0,
        "passport": 2.5,
        "aadhaar": 2.5,
        "government_id": 2.5,
        "physical_addresses": 1.5,
        "phone_numbers": 1.0,
        "dates_of_birth": 1.0,
        "email": 0.5,
        "usernames": 0.3,
    }

    def classify(self, finding_data: Dict[str, Any]) -> ExposureClassification:
        """Classify an exposure finding and calculate its risk score."""
        finding_type = finding_data.get("finding_type", "search_engine")
        exposed_types = [t.lower().replace(" ", "_") for t in finding_data.get("exposed_data_types", [])]

        # Start with base score
        score = self.BASE_SCORES.get(finding_type, 4.0)

        # Add weight for each exposed data type
        for dt in exposed_types:
            score += self.DATA_TYPE_WEIGHTS.get(dt, 0)

        # Cap at 10.0
        score = min(score, 10.0)

        # Determine risk factors
        risk_factors = {
            "identity_theft_risk": any(
                dt in exposed_types for dt in
                ["passwords", "ssn", "government_id", "passport", "aadhaar", "credit_cards"]
            ),
            "financial_risk": any(
                dt in exposed_types for dt in
                ["credit_cards", "bank_account_numbers", "financial"]
            ),
            "reputation_risk": finding_type in ("social_media", "news", "forum", "search_engine"),
            "credential_exposure": any(
                dt in exposed_types for dt in ["passwords", "hashes", "credentials"]
            ),
            "government_id_exposure": any(
                dt in exposed_types for dt in
                ["ssn", "passport", "aadhaar", "government_id", "pan"]
            ),
        }

        # Boost score for high-risk combinations
        if risk_factors["identity_theft_risk"] and risk_factors["credential_exposure"]:
            score = min(score + 1.0, 10.0)

        if risk_factors["government_id_exposure"]:
            score = min(score + 0.5, 10.0)

        # Map score to severity
        severity = self._score_to_severity(score)

        reasoning = self._build_reasoning(finding_type, exposed_types, risk_factors, score)

        return ExposureClassification(
            severity=severity,
            risk_score=round(score, 1),
            risk_factors=risk_factors,
            reasoning=reasoning,
        )

    def _score_to_severity(self, score: float) -> str:
        if score >= 8.0:
            return "critical"
        elif score >= 6.0:
            return "high"
        elif score >= 3.5:
            return "medium"
        return "low"

    def _build_reasoning(
        self,
        finding_type: str,
        exposed_types: List[str],
        risk_factors: Dict[str, bool],
        score: float
    ) -> str:
        parts = [f"Found in {finding_type.replace('_', ' ')} source."]
        if exposed_types:
            parts.append(f"Exposed data: {', '.join(exposed_types[:5])}.")
        if risk_factors.get("credential_exposure"):
            parts.append("Password/credential exposure detected — change affected passwords immediately.")
        if risk_factors.get("identity_theft_risk"):
            parts.append("High identity theft risk due to sensitive identifier exposure.")
        if risk_factors.get("financial_risk"):
            parts.append("Financial data exposed — monitor accounts for unauthorized activity.")
        if risk_factors.get("government_id_exposure"):
            parts.append("Government ID exposed — this is critical and requires immediate action.")
        return " ".join(parts)

    def calculate_overall_exposure_score(
        self, findings: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate an overall exposure score (0-100) from all findings.
        """
        if not findings:
            return 0.0

        active = [
            f for f in findings
            if not f.get("is_false_positive") and not f.get("is_removed")
        ]

        if not active:
            return 0.0

        severity_weights = {"critical": 30, "high": 15, "medium": 6, "low": 2}
        total = sum(severity_weights.get(f.get("severity", "low"), 2) for f in active)
        return min(total, 100.0)
