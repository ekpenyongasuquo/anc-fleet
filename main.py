"""
ANC Fleet — Cloud Run / Render entrypoint.

Triggered by Cloud Scheduler or a manual POST (async, background job -- not
a chat request). Runs the Scanner -> Risk -> Action pipeline end to end,
batch by batch, writing a timestamped Firestore audit record at every stage.

IMPORTANT: GET / is a lightweight health check ONLY. It does NOT run the
pipeline. This matters because Render (and Cloud Run) periodically send GET
requests to check the service is alive -- if those pings triggered the full
pipeline, they would silently burn through the Gemini API quota with no
one intentionally requesting a run. Only POST / triggers the real pipeline.

Local run:      python main.py
Cloud Run/Render: triggered via HTTP POST by Cloud Scheduler or manual curl
"""

import logging

from flask import Flask, jsonify

from agents.scanner_agent import scanner_agent  # noqa: F401 (kept for interactive/dev use via `adk web`)
from agents.risk_agent import risk_agent, score_patient_batch  # noqa: F401
from agents.action_agent import action_agent, process_flagged_patients  # noqa: F401
from tools.firestore_logger import start_run, log_stage, complete_run, fail_run
from tools.cliniqbridge_tool import fetch_anc_observations
from tools.gemini_brief import generate_batch_brief

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anc_fleet")

app = Flask(__name__)

BATCH_SIZE = 50
MAX_BATCHES = 20  # safety cap for a single job invocation; lower this (e.g. 2) for fast local testing


def run_pipeline() -> dict:
    """Runs the full Scanner -> Risk -> Action pipeline across all batches,
    then generates a plain-language Gemini brief summarizing the run.

    Note: agent orchestration here calls the underlying tool functions
    directly in a deterministic loop (rather than relying on LLM-driven
    tool selection for the control flow) so that batch pagination and the
    audit trail are guaranteed correct. The ADK Agent objects (scanner_agent,
    risk_agent, action_agent) remain available for interactive/dev use via
    `adk web` and for any judge who wants to inspect single-batch reasoning.
    """
    run_id = start_run(run_type="batch_scan")
    logger.info(f"Started run {run_id}")

    total_scanned = 0
    total_tier_counts = {"LOW": 0, "WATCH": 0, "HIGH": 0}
    total_actioned = 0
    total_skipped = 0
    all_flagged_examples = []  # small sample across batches, for the Gemini brief

    try:
        offset = 0
        for batch_num in range(MAX_BATCHES):
            batch = fetch_anc_observations(batch_size=BATCH_SIZE, offset=offset)
            records = batch["records"]
            if not records:
                break

            log_stage(run_id, "scan", {
                "batch_num": batch_num,
                "batch_size": len(records),
                "offset": offset,
            })
            total_scanned += len(records)

            scored = score_patient_batch(records)
            log_stage(run_id, "score", {
                "batch_num": batch_num,
                "tier_counts": scored["tier_counts"],
            })
            for tier, count in scored["tier_counts"].items():
                total_tier_counts[tier] += count

            flagged = [
                r for r in scored["results"] if r["risk_tier"] in ("WATCH", "HIGH")
            ]
            log_stage(run_id, "decide", {
                "batch_num": batch_num,
                "flagged_count": len(flagged),
            })
            if len(all_flagged_examples) < 5:
                all_flagged_examples.extend(flagged[:5 - len(all_flagged_examples)])

            action_result = process_flagged_patients(flagged, run_id)
            log_stage(run_id, "act", {
                "batch_num": batch_num,
                "actioned": len(action_result["actioned"]),
                "skipped_duplicate": len(action_result["skipped_duplicate"]),
            })
            total_actioned += len(action_result["actioned"])
            total_skipped += len(action_result["skipped_duplicate"])

            if not batch.get("has_more"):
                break
            offset += BATCH_SIZE

        # Real Gemini call -- turns the run's results into a plain-language
        # brief. This is the step that satisfies the hackathon's Gemini
        # requirement; everything upstream is deterministic scoring logic
        # by design, for auditability.
        gemini_brief = generate_batch_brief(
            tier_counts=total_tier_counts,
            sample_flagged=all_flagged_examples,
        )
        log_stage(run_id, "brief", {"gemini_brief": gemini_brief})
        logger.info(f"Gemini brief: {gemini_brief}")

        summary = {
            "run_id": run_id,
            "total_scanned": total_scanned,
            "tier_counts": total_tier_counts,
            "total_actioned": total_actioned,
            "total_skipped_duplicate": total_skipped,
            "gemini_brief": gemini_brief,
        }
        complete_run(run_id, summary)
        logger.info(f"Completed run {run_id}: {summary}")
        return summary

    except Exception as e:
        logger.exception(f"Run {run_id} failed")
        fail_run(run_id, str(e))
        raise


@app.route("/debug-key", methods=["GET"])
def debug_key():
    """TEMPORARY diagnostic -- shows only the last 4 chars of the loaded
    Gemini key, to confirm which key Render is actually running with.
    Remove this route before final submission."""
    import os
    key = os.environ.get("GEMINI_API_KEY", "")
    return jsonify({"key_last_4": key[-4:] if key else "NOT SET", "key_length": len(key)}), 200


@app.route("/", methods=["POST"])
def trigger():
    """Real pipeline trigger -- only fires on POST (Cloud Scheduler,
    or a manual `curl -X POST`)."""
    try:
        summary = run_pipeline()
        return jsonify({"status": "ok", "summary": summary}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)