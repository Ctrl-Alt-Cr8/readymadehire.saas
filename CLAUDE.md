# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What This Project Is

Readymade.hire SaaS is a multi-user platform built on top of the Readymade.hire job agent engine. The engine fetches job listings, scores them for fit using Claude, generates tailored cover letters, and sends a daily report email. The SaaS layer adds user accounts, per-user config, a web UI, and cost tracking so multiple users can run their own job search agents.

The engine code (in `agent/`) is carried over from the original solo agent repo and is production-tested. Changes to the engine should be surgical — don't restructure it, just extend it.

## Repo Structure

```
agent/    # Python pipeline — Flask server, Claude API, job scoring, cover letters
web/      # Next.js frontend — Firebase Auth, onboarding, dashboard (to be built)
```

## Stack

- **Agent**: Python, Flask, Cloud Run (GCP)
- **AI**: Claude Haiku (scoring) + Claude Sonnet (cover letters) via Anthropic API
- **DB**: Cloud SQL (Postgres) — connection via `DATABASE_URL` env var
- **Auth**: Firebase Auth (ID token verified on agent, Firebase SDK on web)
- **Web**: Next.js, TypeScript, Tailwind CSS
- **CI/CD**: Cloud Build → Cloud Run (agent), Vercel (web)
- **Job sources**: SerpAPI (primary) → Serper.dev (per-keyword fallback)

## Build Plan & Current Status

### Done
- [x] Engine copied from solo agent repo into `agent/` — pipeline is production-tested
- [x] SQLite swapped for Postgres (`psycopg2` + connection pool via `DATABASE_URL`)
- [x] `user_id` threaded through entire pipeline — all DB records are user-scoped from day one
- [x] `run_pipeline(user_id)` and `run()` accept user_id; server.py passes it to background thread

### To Do (in order)

**Task 2 — Per-user config**
Replace hardcoded `PROFILE` dict and `KEYWORDS` list in `agent/app/config.py` with per-user config stored in Postgres. Add a `users` table and `user_configs` table. Pipeline loads profile + keywords by `user_id` at runtime.

**Task 3 — Firebase Auth on `/run-agent`** *(blocked: needs Firebase service account key from user)*
Add Firebase Admin SDK to agent. `/run-agent` endpoint verifies Firebase ID token from `Authorization: Bearer <token>` header, extracts `user_id`, passes it to `run_pipeline()`. Replaces the current `user_id = "default"` placeholder in `server.py`.

**Task 4 — Per-run cost logging**
Capture token usage from Claude API responses in `agent/app/utils/claude_client.py`. Add a `run_logs` table to Postgres. Log Haiku tokens + Sonnet tokens per run and estimate USD cost. This data feeds the dashboard (task 7).

**Task 5 — Scaffold Next.js in `web/`**
Initialize Next.js app with TypeScript + Tailwind. Wire up Firebase Auth (sign-in / sign-out). Basic layout and routing. The user already has an existing Next.js project so they're comfortable with this stack.

**Task 6 — Onboarding flow**
After first sign-in, new users complete onboarding: name, target roles, location preferences, search keywords. Saved to `user_configs` table. Dashboard is gated until onboarding is complete.

**Task 7 — Dashboard**
Main dashboard: list of past runs (date, job counts, cost), job results per run (APPLY/REVIEW/SKIP with details), and a "Run Agent" button that calls `/run-agent` with the Firebase ID token in the Authorization header.

**Task 8 — Deploy agent to Cloud Run** *(blocked: needs Cloud SQL instance from user)*
Set up Cloud Build trigger on `agent/` changes → Docker build → Cloud Run deploy. Configure Cloud SQL connection. Set all env vars in Cloud Run (DATABASE_URL, API keys, Firebase service account).

**Task 9 — Deploy web to Vercel**
Connect `web/` to Vercel. Set env vars (Firebase config, agent Cloud Run URL). Confirm sign-in and dashboard work end-to-end in production.

**Task 10 — Invite first demo users**
Manually create Firebase accounts for curated demo users. Each user completes onboarding and runs the agent. Review cost logs per user to budget scaling. No payments day 1 — invite-only demo, user (Ibrahim) controls access.

## What the User Needs to Do

Before tasks 3 and 8 can be completed, the user needs to:

1. **Create Cloud SQL (Postgres) instance in GCP**
   - Go to Cloud SQL → Create instance → Postgres
   - Name it (e.g. `readymadehire-db`)
   - Create database `readymadehire` and a user (e.g. `agent`)
   - Note the Instance connection name (`project:region:instance-name`)
   - This provides the `DATABASE_URL` for agent env vars

2. **Provide Firebase service account key**
   - Go to Firebase Console → Project Settings → Service Accounts
   - Generate a new private key (JSON)
   - This is needed for Firebase Admin SDK in the agent (`FIREBASE_SERVICE_ACCOUNT` env var)

3. **Rotate all API keys before any public-facing deploy**
   - SerpAPI, Serper.dev, Anthropic, Gmail — rotate and update Cloud Run env vars
   - Move secrets from Cloud Run env vars → GCP Secret Manager before going public

## Agent Architecture & Data Flow

The pipeline in `agent/app/main.py` runs in order:

1. **Fetch** (`sources/fetcher_router.py`): Tries SerpAPI per keyword first; falls back to Serper.dev if SerpAPI returns empty. Both return the same internal dict shape.
2. **Disqualify** (`scoring/filters.py → disqualify_jobs()`): Hard-blocks non-AI, research, and fellowship roles.
3. **Filter** (`scoring/filters.py → passes_filters()`): Soft filters for role type and location. All location logic lives here — never add location filtering elsewhere.
4. **Memory filter** (`storage/job_store.py → is_known_job()`): Skips jobs already seen by this user. Checks by `user_id + title + company`.
5. **Score** (`scoring/scorer.py`): Batches 8 jobs at a time to Claude Haiku. Applies keyword boosts and penalties.
6. **Decide**: Top 20 scored jobs. Score ≥ 88 AND passes `qualifies_for_apply()` → APPLY; 70–87 OR fails qualify → REVIEW; < 70 → SKIP.
7. **Cover letters** (`composer/cover_letter.py`): Claude Sonnet generates letters for APPLY jobs. Two-pass: generate → validate → retry once if needed.
8. **Daily report** (`utils/send_email.py`): One email per run. APPLY section (with cover letter) then REVIEW section.
9. **Record** (`storage/job_store.py → record_job()`): All processed jobs written to Postgres with `user_id`, decision, score, and `email_sent`.

## Database Schema

Current tables:

```sql
-- Tracks all jobs seen and processed per user
CREATE TABLE jobs (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL,
    company    TEXT NOT NULL,
    first_seen DATE NOT NULL,
    last_seen  DATE NOT NULL,
    decision   TEXT,
    email_sent BOOLEAN DEFAULT FALSE,
    score      INTEGER DEFAULT 0
);
```

Tables to add:

```sql
-- One row per registered user
CREATE TABLE users (
    id         TEXT PRIMARY KEY,  -- Firebase UID
    email      TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-user pipeline config (replaces hardcoded PROFILE + KEYWORDS)
CREATE TABLE user_configs (
    user_id         TEXT PRIMARY KEY REFERENCES users(id),
    name            TEXT NOT NULL,
    target_roles    TEXT[],
    location_pref   TEXT,
    keywords        TEXT[],
    summary         TEXT,
    constraints     TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Per-run cost and summary log
CREATE TABLE run_logs (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id),
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    jobs_fetched    INTEGER,
    jobs_apply      INTEGER,
    jobs_review     INTEGER,
    jobs_skip       INTEGER,
    haiku_tokens    INTEGER,
    sonnet_tokens   INTEGER,
    estimated_cost  NUMERIC(8, 4)
);
```

## Environment Variables

All stored in `agent/.env` locally; Cloud Run env vars in production.

```
# Existing (carried over from solo agent)
ANTHROPIC_API_KEY=
SERPAPI_API_KEY=
SERPER_API_KEY=
GMAIL_USER=
GMAIL_APP_PASSWORD=
RECIPIENT_EMAIL=

# New (SaaS)
DATABASE_URL=              # postgres://user:password@host:5432/dbname
USER_ID=                   # Only used for CLI runs (--mock, --dry-run); server uses Firebase UID
FIREBASE_SERVICE_ACCOUNT=  # Path to Firebase Admin SDK JSON key (or JSON string)
```

## Key Configuration (Per-user, once Task 2 is done)

Currently hardcoded in `agent/app/config.py` — these will move to `user_configs` table:
- `PROFILE` dict: name, target roles, location preference, constraints, summary
- `KEYWORDS` list: search terms passed to SerpAPI/Serper

## Claude Model Usage

- **Claude Haiku** (`claude-haiku-4-5-20251001`): Job scoring — cheap, batch-optimized
- **Claude Sonnet** (`claude-sonnet-4-20250514`): Cover letter generation — higher quality

Both called through `utils/claude_client.py`. Shared `_call()` retries up to 3 times with exponential backoff. Token usage from responses should be captured here for cost logging (task 4).

## CLI Flags (agent only)

```bash
python -m app.main [--mock] [--dry-run]
```

| Flag | Data source | DB writes | Claude | Email |
|------|------------|-----------|--------|-------|
| *(none)* | SerpAPI → Serper | yes | full | sends |
| `--mock` | mock_jobs.py | yes | full | prints |
| `--dry-run` | SerpAPI → Serper | no | full | prints |
| `--mock --dry-run` | mock_jobs.py | no | skipped | prints |

`--mock --dry-run` combined is fully offline, zero API cost — use for local testing.

## Architectural Principles (Do Not Violate)

- All location logic lives in `scoring/filters.py` — never add location checks elsewhere
- All DB logic lives in `storage/job_store.py` — never query Postgres directly from other modules
- All Claude calls go through `utils/claude_client.py` — never call the Anthropic SDK directly elsewhere
- Keep the pipeline engine decoupled from any single user's config — no hardcoded personal values in engine code once task 2 is done
- Greenhouse and Lever sources are commented out in `fetcher_router.py` — do not re-enable without investigating the hang issue
- Do not modify the cover letter prompt in `composer/cover_letter.py → _build_cover_letter_prompt()` without checking with the user first

## Running Locally

```bash
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Fully offline test (no API costs, no DB needed)
python -m app.main --mock --dry-run

# Full pipeline (requires .env with all keys + DATABASE_URL)
python -m app.main

# Flask server
python app/server.py
```

## Security Notes

- `/run-agent` currently has a placeholder `user_id = "default"` — Firebase token verification must be implemented (task 3) before any real users are onboarded
- Never commit `.env` or Firebase service account JSON keys
- Before any public-facing deploy: rotate all API keys, implement `/run-agent` auth, move secrets to GCP Secret Manager
