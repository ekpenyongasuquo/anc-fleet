"""
Risk Agent — scores each patient record against the NDHS-grounded feature
weights in scoring/ndhs_weights.py. The scoring itself is deterministic,
transparent Python (not an LLM guess) — the Gemini model's job here is to
orchestrate the scoring tool over a batch and produce a structured summary,
which keeps the actual risk numbers auditable and reproducible rather than
hidden inside a model's reasoning.
"""

from google.adk.agents import Agent

from scoring.ndhs_weights import score_patient, PatientRecord, Education, WealthQuintile, Residence, Region


def score_patient_batch(records: list[dict]) -> dict:
    """ADK function tool: scores a batch of patient records.

    Args:
        records: list of dicts matching the PatientRecord fields (as produced
            by fetch_anc_observations / the synthetic population generator).

    Returns:
        dict with "results": list of scored records (patient_id, risk_tier,
        risk_score, driving_factors), and tier counts for the run summary.
    """
    results = []
    for r in records:
        record = PatientRecord(
            patient_id=r["patient_id"],
            anc_visits_completed=r["anc_visits_completed"],
            maternal_age=r["maternal_age"],
            parity=r["parity"],
            education=Education(r["education"]) if not isinstance(r["education"], Education) else r["education"],
            wealth_quintile=WealthQuintile(r["wealth_quintile"]) if not isinstance(r["wealth_quintile"], WealthQuintile) else r["wealth_quintile"],
            residence=Residence(r["residence"]) if not isinstance(r["residence"], Residence) else r["residence"],
            region=Region(r["region"]) if not isinstance(r["region"], Region) else r["region"],
            distance_to_facility_km=r.get("distance_to_facility_km"),
        )
        result = score_patient(record)
        results.append({
            "patient_id": result.patient_id,
            "risk_tier": result.risk_tier.value,
            "risk_score": result.risk_score,
            "driving_factors": result.driving_factors,
        })

    tier_counts = {"LOW": 0, "WATCH": 0, "HIGH": 0}
    for r in results:
        tier_counts[r["risk_tier"]] += 1

    return {"results": results, "tier_counts": tier_counts}


risk_agent = Agent(
    name="risk_agent",
    model="gemini-3.6-flash",
    instruction=(
        "You are the Risk Agent in the ANC Fleet pipeline. You receive a batch "
        "of patient records and call score_patient_batch to score them against "
        "NDHS-grounded risk weights. Report the tier counts (LOW/WATCH/HIGH) and "
        "flag which patient_ids fall into WATCH or HIGH for the Action Agent to "
        "process. Do not invent risk scores yourself — always use the tool."
    ),
    tools=[score_patient_batch],
)
