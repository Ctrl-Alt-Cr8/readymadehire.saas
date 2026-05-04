import os
import threading
import logging
from flask import Flask, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_pipeline_background():
    """Run the full pipeline in a background thread."""
    try:
        logger.info("🚀 Background pipeline started")
        from app.main import run_pipeline
        run_pipeline()
        logger.info("✅ Background pipeline complete")
    except Exception as e:
        logger.error(f"❌ Background pipeline failed: {e}")


@app.route("/")
def health():
    return {"status": "readymade-hire-agent running"}


@app.route("/run-agent", methods=["POST"])
def run_agent():
    try:
        thread = threading.Thread(target=_run_pipeline_background, daemon=True)
        thread.start()
        logger.info("🚀 Pipeline triggered in background thread")
        return jsonify({"status": "pipeline started", "message": "running in background — check logs for progress"}), 202
    except Exception as e:
        logger.error(f"❌ Failed to start pipeline thread: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
