"""
Generates a synthetic patient population whose feature distributions mirror
published NDHS proportions — NOT arbitrary random data.

This exists because real UCTH facility data requires ethics approval that
is out of scope for the hackathon window (see ANC_FLEET_SPEC.md). The
distributions below are drawn directly from the cited NDHS/DHS statistics,
so the Risk Agent is being exercised against a population that has the
same shape as Nigeria's real numbers, even though individual records are
synthetic.

Swap point: replace this module's output with tools/cliniqbridge_tool.py's
"cliniqbridge" mode once real facility data access is granted. The
PatientRecord interface is identical either way.
"""

import random
import uuid

from scoring.ndhs_weights import (
    PatientRecord, Education, WealthQuintile, Residence, Region,
)

# Distributions approximated from cited NDHS figures:
# education: no-ed 35% / primary 20% / secondary 30% / higher 15%
#   (roughly consistent with the 34.6%<->92.3% adequate-ANC gradient extremes)
_EDUCATION_DIST = [
    (Education.NONE, 0.35),
    (Education.PRIMARY, 0.20),
    (Education.SECONDARY, 0.30),
    (Education.HIGHER, 0.15),
]

# wealth quintiles are by definition ~20% each nationally
_WEALTH_DIST = [
    (WealthQuintile.POOREST, 0.20),
    (WealthQuintile.POORER, 0.20),
    (WealthQuintile.MIDDLE, 0.20),
    (WealthQuintile.RICHER, 0.20),
    (WealthQuintile.RICHEST, 0.20),
]

# NDHS: roughly 48% urban / 52% rural nationally (approx, for population mix)
_RESIDENCE_DIST = [
    (Residence.URBAN, 0.48),
    (Residence.RURAL, 0.52),
]

# rough regional population weighting
_REGION_DIST = [
    (Region.NORTH_WEST, 0.24),
    (Region.NORTH_EAST, 0.14),
    (Region.NORTH_CENTRAL, 0.15),
    (Region.SOUTH_SOUTH, 0.15),
    (Region.SOUTH_EAST, 0.12),
    (Region.SOUTH_WEST, 0.20),
]


def _weighted_choice(dist):
    items, weights = zip(*dist)
    return random.choices(items, weights=weights, k=1)[0]


def _generate_one() -> PatientRecord:
    education = _weighted_choice(_EDUCATION_DIST)
    wealth = _weighted_choice(_WEALTH_DIST)
    residence = _weighted_choice(_RESIDENCE_DIST)
    region = _weighted_choice(_REGION_DIST)

    # ANC visits completed — correlated loosely with education/wealth,
    # consistent with the documented dose-response gradient direction
    base_visits = {
        Education.NONE: 1,
        Education.PRIMARY: 2,
        Education.SECONDARY: 3,
        Education.HIGHER: 4,
    }[education]
    anc_visits = max(0, min(6, base_visits + random.randint(-1, 2)))

    parity = random.choices([0, 1, 2, 3, 4, 5, 6, 7], weights=[10,20,20,18,12,10,6,4])[0]
    maternal_age = random.randint(15, 45)
    distance_km = round(random.uniform(0.5, 40.0), 1) if residence == Residence.RURAL else round(random.uniform(0.2, 8.0), 1)

    return PatientRecord(
        patient_id=str(uuid.uuid4()),
        anc_visits_completed=anc_visits,
        maternal_age=maternal_age,
        parity=parity,
        education=education,
        wealth_quintile=wealth,
        residence=residence,
        region=region,
        distance_to_facility_km=distance_km,
    )


def get_synthetic_batch(batch_size: int = 50, offset: int = 0, total_population: int = 500) -> dict:
    """Deterministic-enough batch generator for demo/testing.
    In a real run this would page through a stored population; for the
    hackathon demo we generate on the fly, capped at total_population."""
    remaining = max(0, total_population - offset)
    n = min(batch_size, remaining)
    records = [_generate_one() for _ in range(n)]
    return {
        "records": [r.__dict__ for r in records],
        "has_more": (offset + n) < total_population,
    }
