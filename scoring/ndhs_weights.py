"""
ANC Paradox risk scoring — weights grounded in published Nigeria DHS findings.

Sources (see ANC_FLEET_SPEC.md for full citations):
- 2024 NDHS: 63% ANC coverage vs 46% skilled birth attendance (~17pt gap)
- 2018 DHS (n=21,792): 74% ANC attendance vs 41% facility delivery (~33pt gap)
- Education gradient: 34.6% (no education) -> 92.3% (higher education) adequate ANC
- Wealth gradient: 30.7% (poorest) -> 89.2% (richest) adequate ANC; aOR 3.93 richest vs poorest
- Urban/rural ANC gap: 76.1% vs 46.0% (crude)
- Parity: home-delivery likelihood rises with parity, falls with wealth
- Maternal age <20: associated with lower facility delivery
- ANC attendance -> facility delivery: OR 2.16 (95% CI 1.99-2.34)
- Northern Nigeria / lowest wealth quintile: pronounced cost/distance "first delay" barrier

This is NOT a black-box ML model trained on unavailable UCTH data. It is a transparent,
literature-grounded scoring function. It is designed to be swapped for a model trained on
real facility data (via CliniqBridge) once institutional ethics approval is granted --
the interface (PatientRecord -> RiskResult) stays the same either way.
"""

from dataclasses import dataclass
from enum import Enum


class RiskTier(str, Enum):
    LOW = "LOW"
    WATCH = "WATCH"
    HIGH = "HIGH"


class WealthQuintile(str, Enum):
    POOREST = "poorest"
    POORER = "poorer"
    MIDDLE = "middle"
    RICHER = "richer"
    RICHEST = "richest"


class Education(str, Enum):
    NONE = "none"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    HIGHER = "higher"


class Residence(str, Enum):
    URBAN = "urban"
    RURAL = "rural"


class Region(str, Enum):
    NORTH_CENTRAL = "north_central"
    NORTH_EAST = "north_east"
    NORTH_WEST = "north_west"
    SOUTH_EAST = "south_east"
    SOUTH_SOUTH = "south_south"
    SOUTH_WEST = "south_west"


@dataclass
class PatientRecord:
    """Minimal feature set — deliberately limited to fields present in both
    public NDHS indicators and typical FHIR Patient/Observation resources,
    so this maps cleanly onto real CliniqBridge data later."""
    patient_id: str
    anc_visits_completed: int
    maternal_age: int
    parity: int
    education: Education
    wealth_quintile: WealthQuintile
    residence: Residence
    region: Region
    distance_to_facility_km: float | None = None


@dataclass
class RiskResult:
    patient_id: str
    risk_tier: RiskTier
    risk_score: float  # 0.0 (lowest risk of non-facility delivery) - 1.0 (highest)
    driving_factors: list[str]


# --- Weight tables, derived from the gradients cited above ---
# Values are illustrative point-scores on a common scale, calibrated so that
# the documented extremes (e.g. poorest+no-education+rural) land in HIGH tier
# and the documented best case (richest+higher-ed+urban) lands in LOW tier.

_EDUCATION_RISK = {
    Education.NONE: 0.65,       # 34.6% adequate ANC attendance -> high risk
    Education.PRIMARY: 0.45,
    Education.SECONDARY: 0.25,
    Education.HIGHER: 0.08,     # 92.3% adequate ANC attendance -> low risk
}

_WEALTH_RISK = {
    WealthQuintile.POOREST: 0.69,   # 30.7% adequate ANC
    WealthQuintile.POORER: 0.50,
    WealthQuintile.MIDDLE: 0.35,
    WealthQuintile.RICHER: 0.20,
    WealthQuintile.RICHEST: 0.11,   # 89.2% adequate ANC
}

_RESIDENCE_RISK = {
    Residence.URBAN: 0.24,   # 76.1% ANC coverage
    Residence.RURAL: 0.54,   # 46.0% ANC coverage
}

# Northern regions carry the documented "first delay" (distance/cost) burden
_REGION_RISK = {
    Region.NORTH_WEST: 0.55,
    Region.NORTH_EAST: 0.55,
    Region.NORTH_CENTRAL: 0.40,
    Region.SOUTH_SOUTH: 0.30,
    Region.SOUTH_EAST: 0.28,
    Region.SOUTH_WEST: 0.22,  # fastest ANC initiation, HR 1.36
}


def _parity_risk(parity: int) -> float:
    """Home-delivery likelihood rises with parity (documented direction,
    not a specific published coefficient) — modeled as a mild step function."""
    if parity <= 1:
        return 0.15
    if parity <= 3:
        return 0.30
    if parity <= 5:
        return 0.45
    return 0.60  # parity 6+ : documented slower ANC initiation (HR 0.77)


def _age_risk(age: int) -> float:
    """Maternal age <20 is documented as associated with lower facility delivery."""
    if age < 20:
        return 0.55
    if age > 40:
        return 0.35
    return 0.15


def _anc_completion_risk(anc_visits_completed: int) -> float:
    """ANC attendance itself strongly predicts facility delivery (OR 2.16).
    Fewer completed visits -> higher risk of non-facility delivery, even though
    the patient may still count as 'attended ANC' at all in aggregate stats."""
    if anc_visits_completed >= 4:
        return 0.10
    if anc_visits_completed >= 2:
        return 0.35
    return 0.60


def _distance_risk(distance_km: float | None) -> float:
    if distance_km is None:
        return 0.0  # unknown — no penalty, avoid false signal
    if distance_km < 5:
        return 0.05
    if distance_km < 15:
        return 0.20
    return 0.40  # documented "first delay" barrier


# Feature weights (relative importance) — sums to 1.0
_FEATURE_WEIGHTS = {
    "education": 0.20,
    "wealth": 0.20,
    "residence": 0.12,
    "region": 0.13,
    "parity": 0.10,
    "age": 0.08,
    "anc_completion": 0.12,
    "distance": 0.05,
}


def score_patient(record: PatientRecord) -> RiskResult:
    component_scores = {
        "education": _EDUCATION_RISK[record.education],
        "wealth": _WEALTH_RISK[record.wealth_quintile],
        "residence": _RESIDENCE_RISK[record.residence],
        "region": _REGION_RISK[record.region],
        "parity": _parity_risk(record.parity),
        "age": _age_risk(record.maternal_age),
        "anc_completion": _anc_completion_risk(record.anc_visits_completed),
        "distance": _distance_risk(record.distance_to_facility_km),
    }

    weighted_score = sum(
        component_scores[k] * _FEATURE_WEIGHTS[k] for k in _FEATURE_WEIGHTS
    )

    # Thresholds calibrated so tier proportions roughly track the real
    # national non-facility-delivery rate (~54-59%, since NDHS reports
    # 41-46% facility delivery) rather than flagging most of the population.
    # See tests/test_scoring.py::test_population_tier_distribution.
    if weighted_score >= 0.48:
        tier = RiskTier.HIGH
    elif weighted_score >= 0.33:
        tier = RiskTier.WATCH
    else:
        tier = RiskTier.LOW

    # Report the top 3 contributing factors for transparency / audit
    top_factors = sorted(
        component_scores.items(),
        key=lambda kv: kv[1] * _FEATURE_WEIGHTS[kv[0]],
        reverse=True,
    )[:3]
    driving_factors = [f"{name} (contribution={score * _FEATURE_WEIGHTS[name]:.3f})"
                        for name, score in top_factors]

    return RiskResult(
        patient_id=record.patient_id,
        risk_tier=tier,
        risk_score=round(weighted_score, 4),
        driving_factors=driving_factors,
    )
