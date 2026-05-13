import io
import json
import os
import sys
import threading
import logging

# When run as `python app/server.py`, Python adds agent/app/ to sys.path instead
# of agent/, so package imports like `from app.storage...` would fail. Fix it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import auth, credentials
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _init_firebase():
    if firebase_admin._apps:
        return
    sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "firebase-service-account.json")
    if os.path.isfile(sa):
        cred = credentials.Certificate(sa)
    else:
        cred = credentials.Certificate(json.loads(sa))
    firebase_admin.initialize_app(cred)


_init_firebase()

from app.storage.job_store import init_db
init_db()


def _verify_token(req) -> tuple[str | None, str | None]:
    """Extract and verify Firebase ID token. Returns (user_id, error_message)."""
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, "Missing Authorization header"
    token = auth_header.split("Bearer ", 1)[1].strip()
    try:
        decoded = auth.verify_id_token(token)
        return decoded["uid"], None
    except auth.ExpiredIdTokenError:
        return None, "Token expired"
    except auth.InvalidIdTokenError:
        return None, "Invalid token"
    except Exception as e:
        return None, f"Auth error: {e}"


def _run_pipeline_background(user_id: str):
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
    user_id, error = _verify_token(request)
    if error:
        return jsonify({"error": error}), 401

    try:
        thread = threading.Thread(target=_run_pipeline_background, args=(user_id,), daemon=True)
        thread.start()
        logger.info(f"🚀 Pipeline triggered for user {user_id}")
        return jsonify({"status": "pipeline started", "message": "running in background — check logs for progress"}), 202
    except Exception as e:
        logger.error(f"❌ Failed to start pipeline thread: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/config", methods=["GET"])
def get_config():
    user_id, error = _verify_token(request)
    if error:
        return jsonify({"error": error}), 401

    try:
        from app.storage.job_store import get_user_config
        cfg = get_user_config(user_id)
        return jsonify({
            "name": cfg.name,
            "target_roles": cfg.target_roles,
            "location_pref": cfg.location_pref,
            "keywords": cfg.keywords,
            "summary": cfg.summary,
            "constraints": cfg.constraints,
            "recipient_email": cfg.recipient_email,
        })
    except ValueError:
        return jsonify({"error": "no config"}), 404
    except Exception as e:
        logger.error(f"❌ /config error for {user_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/parse-resume", methods=["POST"])
def parse_resume():
    user_id, error = _verify_token(request)
    if error:
        return jsonify({"error": error}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    try:
        import pypdf
        pdf_bytes = file.read()
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()

        if len(text) < 100:
            return jsonify({"error": "Could not extract enough text from PDF — try a text-based PDF"}), 422

        interview_answers = request.form.get("interview_answers", "")
        from app.utils.claude_client import parse_resume_with_claude
        parsed = parse_resume_with_claude(text, interview_answers=interview_answers)
        logger.info(f"✅ Resume parsed for user {user_id}")
        return jsonify(parsed)
    except Exception as e:
        logger.error(f"❌ /parse-resume error for {user_id}: {e}")
        return jsonify({"error": f"Resume parsing failed: {e}"}), 500


@app.route("/runs", methods=["GET"])
def get_runs():
    user_id, error = _verify_token(request)
    if error:
        return jsonify({"error": error}), 401

    try:
        from app.storage.job_store import get_runs_with_jobs
        runs = get_runs_with_jobs(user_id)
        return jsonify(runs)
    except Exception as e:
        logger.error(f"❌ /runs error for {user_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/onboard", methods=["POST"])
def onboard():
    user_id, error = _verify_token(request)
    if error:
        return jsonify({"error": error}), 401

    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    recipient_email = (data.get("recipient_email") or "").strip()
    if not recipient_email:
        return jsonify({"error": "recipient_email is required"}), 400

    target_roles = [r.strip() for r in (data.get("target_roles") or []) if r.strip()]
    keywords = [k.strip() for k in (data.get("keywords") or []) if k.strip()]
    location_pref = (data.get("location_pref") or "").strip()
    summary = (data.get("summary") or "").strip()
    constraints = (data.get("constraints") or "").strip()
    interview_answers = (data.get("interview_answers") or "").strip()
    min_salary_k = int(data.get("min_salary_k") or 0)
    years_experience = int(data.get("years_experience") or 0)
    job_type = (data.get("job_type") or "").strip()

    try:
        # Need the user's email — Firebase Admin can look it up from the UID
        firebase_user = auth.get_user(user_id)
        email = firebase_user.email or recipient_email

        from app.storage.job_store import save_user, save_user_config
        save_user(user_id, email)
        save_user_config(
            user_id=user_id,
            name=name,
            target_roles=target_roles,
            location_pref=location_pref,
            keywords=keywords,
            summary=summary,
            constraints=constraints,
            recipient_email=recipient_email,
            interview_answers=interview_answers,
            min_salary_k=min_salary_k,
            years_experience=years_experience,
            job_type=job_type,
        )
        logger.info(f"✅ Onboarding complete for user {user_id}")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"❌ /onboard error for {user_id}: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
