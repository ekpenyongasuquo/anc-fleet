"""
Gemini call via direct API key (Google AI Studio free tier).
Swapped from Vertex AI after confirming the direct API works from Nigeria
without billing verification -- Vertex AI requires billing even for free-tier
Gemini calls, but the direct generativelanguage.googleapis.com endpoint does not.
"""

import os
import logging
import requests

logger = logging.getLogger("anc_fleet.gemini")

_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_MODEL = "gemini-3.6-flash"
_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"


def generate_batch_brief(tier_counts: dict, sample_flagged: list[dict]) -> str:
    """Calls Gemini via direct API key to generate a plain-language ops brief."""

    if not _API_KEY:
        return "[Gemini unavailable: GEMINI_API_KEY not set in environment]"

    examples_text = "\n".join(
        f"- Patient {p['patient_id'][:8]}: {p['risk_tier']} risk, "
        f"top factors: {', '.join(p['driving_factors'][:2])}"
        for p in sample_flagged[:5]
    ) if sample_flagged else "No flagged patients in sample."

    prompt = f"""You are summarizing results from an automated antenatal care (ANC)
risk-screening run for a health facility team in Nigeria. Write a short brief
(under 120 words) a busy health worker could read in 20 seconds.

Batch results:
- HIGH risk (needs urgent call): {tier_counts.get('HIGH', 0)}
- WATCH (needs SMS follow-up): {tier_counts.get('WATCH', 0)}
- LOW risk: {tier_counts.get('LOW', 0)}

Example flagged patients and their top risk drivers:
{examples_text}

Write the brief in plain, direct language. No headers, no bullet points.
Mention the most common risk driver you see in the examples."""

    try:
        response = requests.post(
            f"{_API_URL}?key={_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.exception("Gemini brief generation failed")
        return (
            f"[Gemini unavailable this run: {e}] "
            f"Raw counts -- HIGH: {tier_counts.get('HIGH', 0)}, "
            f"WATCH: {tier_counts.get('WATCH', 0)}, "
            f"LOW: {tier_counts.get('LOW', 0)}"
        )