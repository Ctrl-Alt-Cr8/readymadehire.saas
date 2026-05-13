-- Migration 001: users and user_configs tables
-- Run this once against your Cloud SQL instance before first deploy.

CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_configs (
    user_id         TEXT PRIMARY KEY REFERENCES users(id),
    name            TEXT NOT NULL,
    target_roles    TEXT[],
    location_pref   TEXT,
    keywords        TEXT[],
    summary         TEXT,
    constraints     TEXT,
    recipient_email TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
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

CREATE INDEX IF NOT EXISTS idx_jobs_user_title_company
    ON jobs (user_id, lower(title), lower(company));

-- Seed default CLI user (used for local --mock / --dry-run runs)
INSERT INTO users (id, email)
VALUES ('default', 'iheartfreeart@gmail.com')
ON CONFLICT (id) DO NOTHING;

INSERT INTO user_configs (
    user_id, name, target_roles, location_pref,
    keywords, summary, constraints, recipient_email
)
VALUES (
    'default',
    'Ibrahim Siddiq',
    ARRAY['Prompt Engineer', 'AI Agent Engineer', 'Automation Engineer', 'Creative Technologist'],
    'Remote preferred',
    ARRAY[
        'ai agent engineer', 'prompt engineer', 'llm engineer',
        'ai automation engineer', 'generative ai engineer',
        'applied ai engineer', 'creative technologist ai', 'founding ai engineer'
    ],
    'AI systems builder focused on Readymade.AI-style products, LLM orchestration, and practical deployment of production agents.',
    'No agencies, remote/hybrid only',
    'iheartfreeart@gmail.com'
)
ON CONFLICT (user_id) DO NOTHING;
