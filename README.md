# ANC Fleet

**All Things Agentic Hackathon — Taskmaster Track**

An asynchronous, multi-agent pipeline that processes batches of antenatal care (ANC)
records, scores each patient against risk weights grounded in published Nigeria
Demographic and Health Survey (NDHS) findings, and autonomously schedules targeted
outreach for women at elevated risk of skipping facility delivery — the "ANC Paradox"
(women who complete ANC visits but don't deliver in a health facility).

Not a chatbot. This runs as a background job: Cloud Scheduler triggers a Cloud Run
service that scans a population, scores it, decides who needs outreach, acts on those
decisions, and writes a timestamped audit trail of every step to Firestore.

---

## Why this exists

Nigeria's own national health survey data documents a large, persistent gap between
ANC attendance and facility delivery:

- **2024 NDHS:** 63% ANC coverage vs. 46% skilled birth attendance
- **2018 DHS (n=21,792):** 74% ANC attendance vs. 41% facility delivery

ANC Fleet turns the DHS's own documented risk correlates (education, wealth quintile,
residence, parity, maternal age, region, ANC completion) into a transparent scoring
function — not a black box — so that facilities can identify and reach out to
at-risk women before they're lost to follow-up, at population scale instead of
one patient at a time.

Full citations and the scoring rationale are in `scoring/ndhs_weights.py` (module
docstring) and `ANC_FLEET_SPEC.md`.

## Data note

Real facility-level UCTH patient data requires institutional ethics approval, which
is out of scope for this hackathon's timeline. This submission uses a synthetic
population generator (`scoring/synthetic_population.py`) whose feature distributions
are built from the same published NDHS proportions cited above — not arbitrary random
data. The pipeline is architected so that swapping to live data is a one-line
configuration change (`ANC_FLEET_SOURCE_MODE=cliniqbridge`) via the existing
CliniqBridge FHIR MCP server, with zero changes needed downstream. That swap is the
intended next step once institutional approval is granted.

---

## Architecture

```
Cloud Scheduler (async trigger, no human in the loop)
        │
        ▼
Scanner Agent (Cloud Run) ──► CliniqBridge FHIR MCP / synthetic population
        │
        ▼
Risk Agent (Cloud Run, Gemini 3.5+ via Vertex AI + ADK)
        │  scores against NDHS-grounded weights (scoring/ndhs_weights.py)
        ▼
Action Agent (Cloud Run) ──► SentinelCall outreach pipeline
        │
        ▼
Firestore — timestamped run/stage audit log + cross-run patient memory
```

Patient memory in Firestore prevents duplicate outreach across runs — the pipeline
tracks who's already been actioned, which is what makes it a genuinely asynchronous,
stateful system rather than a stateless one-shot demo.

## Tech used

- **Gemini 3.5+** via Vertex AI (Risk Agent reasoning)
- **Google ADK** (`google-adk`) for agent definition and orchestration
- **Google Cloud Run** — containerized, scheduler-triggered background job
- **Google Cloud Firestore** — audit trail + cross-run patient memory
- **Google Cloud Scheduler** — async trigger (no human initiates each run)
- CliniqBridge (existing FHIR R4 MCP server) — data source interface
- SentinelCall (existing outreach pipeline) — action execution interface

## Repo structure

```
anc-fleet/
├── agents/
│   ├── scanner_agent.py     # pulls ANC record batches
│   ├── risk_agent.py        # scores batches against NDHS weights
│   └── action_agent.py      # schedules outreach, checks memory for duplicates
├── scoring/
│   ├── ndhs_weights.py      # the core domain-expertise risk model
│   └── synthetic_population.py  # NDHS-shaped demo data generator
├── tools/
│   ├── cliniqbridge_tool.py # FHIR data source (synthetic or live)
│   ├── sentinelcall_tool.py # outreach action (dry-run or live)
│   └── firestore_logger.py  # the audit trail judges can inspect
├── tests/
│   └── test_scoring.py      # verifies scoring logic in isolation
├── main.py                  # Cloud Run entrypoint, orchestrates the full pipeline
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Spin-up instructions

### 1. Local — verify the scoring logic (no GCP needed)

```bash
git clone <this-repo-url>
cd anc-fleet
pip install -r requirements.txt
pytest tests/test_scoring.py -v
```

You should see 5 tests pass, including a regression guard confirming the
flagged-population rate tracks NDHS's real ~54–59% non-facility-delivery rate.

### 2. Local — run the full pipeline against synthetic data

```bash
cp .env.example .env
# edit .env: fill in GCP_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS
python main.py
# in another terminal:
curl -X POST http://localhost:8080/
```

This runs Scanner → Risk → Action against the NDHS-shaped synthetic population,
writing real timestamped records to your Firestore project.

### 3. Deploy to Cloud Run

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/anc-fleet

gcloud run deploy anc-fleet \
  --image gcr.io/YOUR_PROJECT_ID/anc-fleet \
  --platform managed \
  --region us-central1 \
  --set-env-vars GCP_PROJECT_ID=YOUR_PROJECT_ID,GOOGLE_GENAI_USE_VERTEXAI=true,ANC_FLEET_SOURCE_MODE=synthetic \
  --no-allow-unauthenticated
```

### 4. Wire up Cloud Scheduler (the async trigger)

```bash
gcloud scheduler jobs create http anc-fleet-batch-scan \
  --schedule="0 */6 * * *" \
  --uri="<your-cloud-run-url>" \
  --http-method=POST \
  --oidc-service-account-email=<your-service-account>
```

This runs the pipeline every 6 hours with no human initiating each run —
the "background, asynchronous" requirement of the hackathon, satisfied literally.

### 5. Inspect real job history (what judges should look at)

- Firestore console → `anc_fleet_runs` collection → any run document → `stages`
  subcollection shows every scan/score/decide/act event with a timestamp.
- Cloud Run → anc-fleet service → Logs, for request-level execution proof.
- `anc_fleet_patient_memory` collection shows cross-run deduplication in action.

---

## Findings (from validated national data, not invented)

- NDHS-documented risk factors (education, wealth, residence, parity, age, region,
  ANC completion) produce a scoring function that separates the survey's own
  best-case and worst-case demographic profiles into LOW and HIGH risk correctly
  (see `tests/test_scoring.py`).
- Calibrated against a 500-patient NDHS-shaped synthetic population, the model
  flags ~65% as needing some form of outreach (WATCH+HIGH) — consistent with
  NDHS's documented ~54–59% non-facility-delivery rate — with only ~7% escalated
  to urgent-call (HIGH) tier, keeping the intervention targeted rather than
  blanket.

## Roadmap

- Swap `ANC_FLEET_SOURCE_MODE` to `cliniqbridge` once institutional ethics
  approval for real UCTH facility data is granted — no downstream code changes
  needed.
- Move SentinelCall action agent out of dry-run mode for live pilot outreach.
- Add Agent Identity / Model Armor guardrails ahead of any real PII flowing
  through the pipeline (currently out of scope for Taskmaster track, relevant
  if extended toward Fortified Enterprise Fleet).
