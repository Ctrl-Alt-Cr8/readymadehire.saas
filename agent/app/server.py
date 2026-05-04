import os
import threading
import logging
from flask import Flask, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_pipeline_background(user_id: str):
    """Run the full pipeline in a background thread."""
    try:
        logger.info(f"🚀 Background pipeline started for user {user_id}")
        from app.main import run_pipeline
        run_pipeline(user_id=user_id)
        logger.info(f"✅ Background pipeline complete for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Background pipeline failed for user {user_id}: {e}")


@app.route("/")
def health():
    return {"status": "readymade-hire-agent running"}


@app.route("/run-agent", methods=["POST"])
def run_agent():
    # TODO (task 3): verify Firebase ID token and extract real user_id
    user_id = "default"
    try:
        thread = threading.Thread(target=_run_pipeline_background, args=(user_id,), daemon=True)
        thread.start()
        logger.info(f"🚀 Pipeline triggered for user {user_id}")
        return jsonify({"status": "pipeline started", "message": "running in background — check logs for progress"}), 202
    except Exception as e:
        logger.error(f"❌ Failed to start pipeline thread: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
