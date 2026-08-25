# ANC Fleet — Project Spec
### All Things Agentic Hackathon — Taskmaster Track — Deadline Sep 1, 2026

---

## 1. The Problem (grounded in real data)

Nigeria has a documented, quantified maternal health paradox: women complete antenatal
care visits, but a large share still do not deliver in a health facility.

**National scale of the gap (real NDHS figures):**

| Survey | ANC coverage | Facility/skilled delivery | Gap |
|---|---|---|---|
| 2024 NDHS | 63% ANC coverage | 46% skilled birth attendance | ~17 pts |
| 2018 DHS (21,792 women) | 74% attended ANC | 41% delivered in facility | ~33 pts |
| 2023 trend | 68% had 4+ ANC visits (up from 57% in 2018) | 52% skilled birth attendance (up from 43%) | narrowing, still large |

**Documented predictors of the gap (real regression findings, usable as model features):**

| Factor | Effect | Source finding |
|---|---|---|
| Education | Dose-response gradient | Adequate ANC attendance: 34.6% (no education) → 92.3% (higher education) |
| Wealth quintile | Dose-response gradient | Adequate ANC attendance: 30.7% (poorest) → 89.2% (richest); aOR = 3.93 richest vs poorest for ANC timing |
| Residence | Urban/rural gap | Crude ANC gap 76.1% (urban) vs 46.0% (rural) |
| Parity | Higher parity → higher home-delivery risk | Home delivery likelihood increases with parity, decreases with wealth |
| Maternal age | <20 yrs → higher home-delivery risk | Younger age at first birth associated with lower facility delivery |
| Region | Regional variation in initiation speed | South West fastest ANC initiation (HR 1.36); parity 6+ slower (HR 0.77) |
| ANC attendance itself | Strong predictor of facility delivery | OR = 2.16 (95% CI 1.99–2.34) for ANC → facility delivery |
| Distance/cost/infrastructure | "First delay" barrier | Pronounced in northern Nigeria, lowest wealth quintile |

These are the feature weights the Risk Agent uses — not invented, not synthetic guesses.

**Framing for judges:** ANC Fleet is trained and validated against real, published national
indicators (2024/2023 NDHS), and architected to plug into live facility-level FHIR data via
CliniqBridge (already built and live) once institutional ethics approval is granted. This is
an honest "future work" story, not a data-access gap disguised as a feature.

---

## 2. What ANC Fleet Does

Not a single-patient chatbot. A background pipeline that processes a population of ANC
records at once, flags the ones matching the paradox pattern, and autonomously executes an
intervention — with every step logged and timestamped for audit.

**Three agents, one async pipeline:**

1. **Scanner Agent**
   - Pulls ANC visit records via CliniqBridge (existing FHIR MCP server)
   - Runs as a Cloud Scheduler-triggered, async Cloud Run job — not request/response
   - Batches records for processing, not one-at-a-time

2. **Risk Agent** (Gemini 3.5 via Vertex AI + ADK — replaces the Groq logic used in SentinelCall)
   - Scores each record against the NDHS-derived feature weights above
   - Outputs a risk tier (e.g. LOW / WATCH / HIGH) with the specific factors driving the score
   - This is where the domain-expertise moat lives — the weights are real, not arbitrary

3. **Action Agent**
   - For WATCH/HIGH tier patients: schedules outreach (reuses SentinelCall's caller logic)
   - Writes a structured record of what action was taken and why
   - Does NOT re-flag patients already actioned in a prior run (checked against Memory)

**Persistent state (Memory Bank equivalent):**
Firestore collection tracks each patient across weeks so re-runs don't duplicate outreach —
this is what proves "operates beyond standard chat loops."

**Audit trail (the fix for the MaternaFlow lesson):**
Every step — scan → score → decision → action — writes a timestamped Firestore record from
day one of development, not bolted on before submission. This is what a judge clicks into
to see real job history instead of a diagram.

---

## 3. Architecture

```
Cloud Scheduler (async trigger)
        │
        ▼
Scanner Agent (Cloud Run) ──► CliniqBridge (FHIR MCP, existing)
        │
        ▼
Risk Agent (Cloud Run, Gemini 3.5 + ADK) ──► NDHS-weighted scoring logic
        │
        ▼
Action Agent (Cloud Run) ──► SentinelCall outreach logic (existing)
        │
        ▼
Firestore ── timestamped job history / audit log / patient memory
```

**Required hackathon tech checklist:**
- [ ] Gemini 3.5+ via Vertex AI — Risk Agent
- [ ] Google Agent Framework — ADK (or GenKit) for agent orchestration
- [ ] Google Cloud infra — Cloud Run + Firestore + Cloud Scheduler
- [ ] $150 credit form submitted (cloud.google.com/free + hackathon credit form)

---

## 4. Build Plan (Aug 9 → Sep 1)

**Week 1 (Aug 9–15) — De-risk the unknowns first**
- [ ] GCP project set up, credits claimed, Vertex AI / Cloud Run / Firestore / Scheduler enabled
- [ ] One real curl-tested call to Gemini 3.5 via Vertex AI working (before any wrapper code)
- [ ] ADK (or GenKit) skeleton deployed to Cloud Run — confirm reachable end to end
- [ ] Hard-code the NDHS feature weights table above into a scoring module

**Week 2 (Aug 16–22) — Wire the three agents for real execution**
- [ ] Scanner Agent: batch pull via CliniqBridge, async Cloud Run job
- [ ] Risk Agent: port scoring logic to Gemini/ADK, output risk tier + driving factors
- [ ] Action Agent: reuse SentinelCall outreach logic, triggered by Risk Agent output
- [ ] Firestore logging wired in from the start — every step, every run, timestamped

**Week 3 (Aug 23–29) — Proof, polish, submission assets**
- [ ] Run real batch jobs against NDHS-grounded synthetic population data; capture before/after numbers
- [ ] Architecture diagram (the pipeline above, rendered cleanly)
- [ ] ~4-min demo video: open on real numbers from a real run, show Cloud Run dashboard / job history live, not slides
- [ ] README with spin-up instructions + a findings section stating the real pattern validated
- [ ] Buffer: Aug 30–31 for submission mechanics

---

## 5. Why This Wins (vs. past submissions)

| Past failure | Fix in ANC Fleet |
|---|---|
| MaternaFlow: diagram, not orchestration; no real job history | Firestore timestamped logs from day 1; judges click into real Cloud Run history |
| DevGuard: Nigeria-specific read as narrow vs global entrants | Reframed as a domain-data moat — real regression-backed weights most teams can't replicate |
| SentinelPilot: lost to teams with measurable before/after on real data | Demo opens with real batch-run numbers, not narration |
| General pattern: light-weight, single happy-path demos | Three-stage async pipeline with persistent memory — genuinely beyond a chat loop |

---

## 6. Open Items to Track

- [ ] Confirm David/SignalDrop IAM resolved or fully decoupled from this project's GCP account (should be independent — own GCP project + $150 credit)
- [ ] Decide: synthetic population generation approach (should mirror NDHS distributions, not be arbitrary random data)
- [ ] Confirm ADK vs GenKit choice before Week 1 build starts
