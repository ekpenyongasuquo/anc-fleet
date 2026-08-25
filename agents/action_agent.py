"""
Action Agent — for WATCH/HIGH tier patients, checks Firestore memory to
avoid duplicate outreach across runs, then schedules outreach via
SentinelCall. This is the agent that makes the pipeline genuinely
asynchronous/stateful across weeks rather than a stateless one-shot demo.
"""

from google.adk.agents import Agent

from tools.sentinelcall_tool import schedule_outreach
from tools.firestore_logger import was_already_actioned, record_action_taken


def process_flagged_patients(flagged_patients: list[dict], run_id: str) -> dict:
    """ADK function tool: processes WATCH/HIGH patients — skips anyone
    already actioned in a prior run, otherwise schedules outreach and
    records the action in persistent memory.

    Args:
        flagged_patients: list of dicts with patient_id, risk_tier, driving_factors.
        run_id: the current pipeline run's ID, for audit linkage.

    Returns:
        dict with "actioned": list of patients newly actioned this run,
        "skipped_duplicate": list of patient_ids already actioned before.
    """
    action_type = "outreach"
    actioned = []
    skipped = []

    for p in flagged_patients:
        patient_id = p["patient_id"]
        if was_already_actioned(patient_id, action_type):
            skipped.append(patient_id)
            continue

        result = schedule_outreach(
            patient_id=patient_id,
            risk_tier=p["risk_tier"],
            driving_factors=p.get("driving_factors", []),
        )
        record_action_taken(patient_id, action_type, run_id, result)
        actioned.append(result)

    return {"actioned": actioned, "skipped_duplicate": skipped}


action_agent = Agent(
    name="action_agent",
    model="gemini-3.6-flash",
    instruction=(
        "You are the Action Agent in the ANC Fleet pipeline. You receive the "
        "list of WATCH/HIGH risk patients from the Risk Agent and call "
        "process_flagged_patients to schedule outreach for them, skipping "
        "anyone already actioned in a previous run. Report how many patients "
        "were newly actioned versus skipped as duplicates."
    ),
    tools=[process_flagged_patients],
)
