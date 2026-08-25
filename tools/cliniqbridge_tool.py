"""
Wraps the existing CliniqBridge FHIR MCP server (cliniqbridge.onrender.com)
as an ADK function tool, so the Scanner Agent can pull ANC observation
records the same way SentinelCall and MaternaFlow already do.

NOTE: In the hackathon demo, this defaults to a synthetic population
generator (see scoring/synthetic_population.py) that mirrors NDHS
distributions, because real UCTH patient data requires ethics approval
that is out of scope for this submission window. Swapping SOURCE_MODE to
"cliniqbridge" switches to live FHIR pulls with zero interface change to
downstream agents — that swap is the intended post-hackathon path once
institutional approval is granted.
"""

import os
import requests

CLINIQBRIDGE_BASE_URL = os.environ.get(
    "CLINIQBRIDGE_BASE_URL", "https://cliniqbridge.onrender.com"
)
SOURCE_MODE = os.environ.get("ANC_FLEET_SOURCE_MODE", "synthetic")  # "synthetic" | "cliniqbridge"


def fetch_anc_observations(batch_size: int = 50, offset: int = 0) -> dict:
    """ADK function tool: fetches a batch of ANC-related FHIR Observation
    records for the Scanner Agent to process.

    Args:
        batch_size: number of records to pull in this batch.
        offset: pagination offset for batch processing of large populations.

    Returns:
        dict with "records": list of raw observation dicts, and "has_more": bool
    """
    if SOURCE_MODE == "cliniqbridge":
        resp = requests.get(
            f"{CLINIQBRIDGE_BASE_URL}/get_observations",
            params={"category": "anc", "limit": batch_size, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "records": data.get("observations", []),
            "has_more": data.get("has_more", False),
        }

    # synthetic mode — see scoring/synthetic_population.py for generation logic
    from scoring.synthetic_population import get_synthetic_batch
    return get_synthetic_batch(batch_size=batch_size, offset=offset)
