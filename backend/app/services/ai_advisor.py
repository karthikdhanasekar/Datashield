"""
DataShield OSINT - AI Privacy Advisor
Uses OpenAI to explain risks, suggest actions, and recommend privacy settings
"""
from typing import List, Dict, Any, AsyncGenerator
from structlog import get_logger

from app.core.config import settings

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are DataShield AI — an expert privacy and cybersecurity advisor integrated 
into the DataShield OSINT platform.

Your role is to:
1. Explain privacy risks in plain, non-technical language
2. Suggest concrete next actions to protect the user
3. Recommend privacy settings for social media and online accounts
4. Explain relevant legal rights (GDPR, CCPA, right to be forgotten)
5. Prioritize incidents by urgency and impact
6. Maintain a calm, reassuring tone

You must NEVER:
- Suggest illegal activities
- Provide hacking or unauthorized access instructions
- Make definitive legal advice (recommend consulting a lawyer)
- Share or request personal information beyond what is provided

Always be concise, actionable, and supportive.
"""


async def get_ai_advice(
    user_message: str,
    context: Dict[str, Any] = None,
) -> str:
    """Get AI privacy advice for a user query."""
    if not settings.OPENAI_API_KEY:
        return _fallback_advice(user_message, context)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        context_str = _build_context_string(context) if context else ""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        if context_str:
            messages.append({
                "role": "system",
                "content": f"User's current exposure context:\n{context_str}",
            })

        messages.append({"role": "user", "content": user_message})

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.7,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error("AI advice failed", error=str(e))
        return _fallback_advice(user_message, context)


async def analyze_findings(findings: List[Dict]) -> str:
    """Generate an AI summary and action plan from scan findings."""
    if not settings.OPENAI_API_KEY:
        return _fallback_findings_analysis(findings)

    if not findings:
        return "No exposures found. Keep monitoring and maintain good privacy hygiene."

    findings_summary = "\n".join([
        f"- [{f.get('severity', 'unknown').upper()}] {f.get('source_domain', 'unknown')}: "
        f"{f.get('finding_type', '')} — {', '.join(f.get('exposed_data_types', []))}"
        for f in findings[:20]
    ])

    prompt = f"""Based on the following privacy exposure findings, provide:
1. A clear risk summary (2-3 sentences)
2. The top 3 most urgent actions to take
3. Long-term privacy recommendations

Findings:
{findings_summary}
"""

    return await get_ai_advice(prompt)


def _build_context_string(context: Dict) -> str:
    parts = []
    if context.get("exposure_score"):
        parts.append(f"Overall exposure score: {context['exposure_score']}/100")
    if context.get("total_findings"):
        parts.append(f"Total findings: {context['total_findings']}")
    if context.get("critical_count"):
        parts.append(f"Critical findings: {context['critical_count']}")
    if context.get("risk_level"):
        parts.append(f"Risk level: {context['risk_level']}")
    return "\n".join(parts)


def _fallback_advice(message: str, context: Dict = None) -> str:
    """Fallback advice when OpenAI is not configured."""
    if "password" in message.lower() or "breach" in message.lower():
        return (
            "If your password was exposed in a breach, change it immediately on the affected site "
            "and any other sites where you used the same password. Enable two-factor authentication "
            "(2FA) and use a password manager to generate unique, strong passwords."
        )
    if "gdpr" in message.lower() or "removal" in message.lower():
        return (
            "Under GDPR (in the EU) and similar laws worldwide, you have the right to request "
            "removal of your personal data. Use our Takedown Request feature to automatically "
            "generate the appropriate legal request. The website typically has 30 days to respond."
        )
    return (
        "Based on your exposure findings, I recommend: "
        "1) Request removal of any critical or high-severity exposures immediately using our takedown tool. "
        "2) Enable continuous monitoring to detect new exposures. "
        "3) Review your social media privacy settings. "
        "4) Use unique passwords and enable MFA on all accounts. "
        "5) Consider filing a formal complaint for unresolved exposures."
    )


def _fallback_findings_analysis(findings: List) -> str:
    n = len(findings)
    if n == 0:
        return "No exposures found. Your digital footprint appears clean."
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    high = sum(1 for f in findings if f.get("severity") == "high")
    return (
        f"Found {n} exposure(s): {critical} critical, {high} high severity. "
        "Priority actions: 1) Request removal of critical exposures immediately. "
        "2) Change any exposed passwords. 3) Enable monitoring on active findings. "
        "4) Review our takedown request templates to contact affected websites."
    )
