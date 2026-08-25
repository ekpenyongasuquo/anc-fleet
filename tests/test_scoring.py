"""
Run with: pytest tests/test_scoring.py -v

These tests verify the NDHS-grounded scoring logic in isolation, before any
GCP/ADK/Firestore setup is needed — the first thing to confirm works.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring.ndhs_weights import (
    score_patient, PatientRecord, RiskTier,
    Education, WealthQuintile, Residence, Region,
)


def test_best_case_profile_scores_low():
    """Richest + higher education + urban + good ANC completion should be LOW risk,
    consistent with NDHS's 89.2%/92.3% adequate-ANC figures for this group."""
    record = PatientRecord(
        patient_id="test-best-case",
        anc_visits_completed=4,
        maternal_age=28,
        parity=1,
        education=Education.HIGHER,
        wealth_quintile=WealthQuintile.RICHEST,
        residence=Residence.URBAN,
        region=Region.SOUTH_WEST,
        distance_to_facility_km=2.0,
    )
    result = score_patient(record)
    assert result.risk_tier == RiskTier.LOW, f"Expected LOW, got {result.risk_tier} (score={result.risk_score})"


def test_worst_case_profile_scores_high():
    """Poorest + no education + rural + poor ANC completion + high parity should
    be HIGH risk, consistent with NDHS's 30.7%/34.6% adequate-ANC figures."""
    record = PatientRecord(
        patient_id="test-worst-case",
        anc_visits_completed=1,
        maternal_age=18,
        parity=6,
        education=Education.NONE,
        wealth_quintile=WealthQuintile.POOREST,
        residence=Residence.RURAL,
        region=Region.NORTH_WEST,
        distance_to_facility_km=30.0,
    )
    result = score_patient(record)
    assert result.risk_tier == RiskTier.HIGH, f"Expected HIGH, got {result.risk_tier} (score={result.risk_score})"


def test_driving_factors_populated():
    record = PatientRecord(
        patient_id="test-factors",
        anc_visits_completed=2,
        maternal_age=22,
        parity=3,
        education=Education.PRIMARY,
        wealth_quintile=WealthQuintile.POORER,
        residence=Residence.RURAL,
        region=Region.NORTH_EAST,
        distance_to_facility_km=12.0,
    )
    result = score_patient(record)
    assert len(result.driving_factors) == 3
    assert all(isinstance(f, str) for f in result.driving_factors)


def test_unknown_distance_does_not_crash():
    record = PatientRecord(
        patient_id="test-no-distance",
        anc_visits_completed=3,
        maternal_age=25,
        parity=2,
        education=Education.SECONDARY,
        wealth_quintile=WealthQuintile.MIDDLE,
        residence=Residence.URBAN,
        region=Region.SOUTH_SOUTH,
        distance_to_facility_km=None,
    )
    result = score_patient(record)
    assert result.risk_score is not None


def test_population_tier_distribution_matches_national_rate():
    """Regression guard: the synthetic population's flagged rate (WATCH+HIGH)
    should track the real NDHS non-facility-delivery rate (~54-65%, since
    NDHS reports 41-46% facility delivery), not drift toward flagging
    almost everyone or almost no one. This test exists because an earlier
    threshold calibration flagged 83% of the population -- too aggressive
    to be credible as a targeted intervention tool."""
    from scoring.synthetic_population import get_synthetic_batch

    batch = get_synthetic_batch(batch_size=500, offset=0, total_population=500)
    tier_counts = {"LOW": 0, "WATCH": 0, "HIGH": 0}
    for r in batch["records"]:
        pr = PatientRecord(
            patient_id=r["patient_id"], anc_visits_completed=r["anc_visits_completed"],
            maternal_age=r["maternal_age"], parity=r["parity"], education=r["education"],
            wealth_quintile=r["wealth_quintile"], residence=r["residence"], region=r["region"],
            distance_to_facility_km=r["distance_to_facility_km"],
        )
        result = score_patient(pr)
        tier_counts[result.risk_tier.value] += 1

    flagged_pct = (tier_counts["WATCH"] + tier_counts["HIGH"]) / 500 * 100
    assert 45 <= flagged_pct <= 70, (
        f"Flagged rate {flagged_pct:.1f}% is out of the credible range "
        f"(45-70%, targeting NDHS's ~54-59% non-facility-delivery rate). "
        f"Tier counts: {tier_counts}"
    )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
