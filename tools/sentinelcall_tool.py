"""
Wraps SentinelCall's existing outreach/caller logic as an ADK function tool
for the Action Agent. Reuses the proven caller pipeline from the CALL-E
hackathon submission rather than rebuilding outreach from scratch.
"""

import os
import requests

SENTINELCALL_BASE_URL = os.environ.get("SENTINELCALL_BASE_URL", "")
DRY_RUN = os.environ.get("ANC_FLEET_DRY_RUN", "true").lower() == "true"


def schedule_outreach(patient_id: str, risk_tier: str, driving_factors: list[str]) -> dict:
    """ADK function tool: schedules a follow-up outreach action for a
    WATCH/HIGH tier patient via SentinelCall.

    Args:
        patient_id: the patient identifier to reach out to.
        risk_tier: "WATCH" or "HIGH" — determines outreach urgency/script.
        driving_factors: top risk factors, used to tailor the outreach message.

    Returns:
        dict describing the action taken, for audit logging.
    """
    action_payload = {
        "patient_id": patient_id,
        "risk_tier": risk_tier,
        "driving_factors": driving_factors,
        "action_type": "urgent_call" if risk_tier == "HIGH" else "sms_reminder",
    }

    if DRY_RUN or not SENTINELCALL_BASE_URL:
        # Safe default for hackathon demo runs — still logs the decision,
        # just doesn't place a real call/SMS. Flip ANC_FLEET_DRY_RUN=false
        # and set SENTINELCALL_BASE_URL to go live.
        return {**action_payload, "status": "dry_run_logged"}

    resp = requests.post(
        f"{SENTINELCALL_BASE_URL}/schedule_outreach",
        json=action_payload,
        timeout=30,
    )
    resp.raise_for_status()
    return {**action_payload, "status": "dispatched", "response": resp.json()}
