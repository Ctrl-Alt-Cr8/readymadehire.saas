"""Job relevance scoring powered by Claude."""

from __future__ import annotations

import json

from app.config import PROFILE
from app.utils.claude_client import call_claude_haiku


DEFAULT_SCORE = {
    "score": 0,
    "why_fit": "Unable to score this job right now.",
    "best_angle": "No angle available.",
    "gaps": "Could not evaluate gaps.",
}

PRIORITY_KEYWORDS = [
    "llm", "large language model", "prompt", "prompt engineering",
    "agent", "ai agent", "automation", "workflow", "orchestration",
    "api integration", "integrations", "openai", "anthropic", "claude",
    "generative ai", "gpt", "ai systems", "ai applications", "prototype",
    "prototyping", "rapid iteration", "developer tools",
]

PENALTY_KEYWORDS = [
    "phd required", "statistics", "model training", "computer vision",
    "research publication", "research agenda", "theoretical",
]


def _extract_json_payload(raw_text: str) -> str:
    """Extract a JSON object or array from raw model output."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def _apply_boosts(parsed: dict, combined_text: str) -> dict:
    """Apply keyword boost and penalty to a parsed score dict."""
    score = int(float(parsed["score"]))
    boost = sum(3 for k in PRIORITY_KEYWORDS if k in combined_text)
    score += min(boost, 18)
    penalty = sum(8 for k in PENALTY_KEYWORDS if k in combined_text)
    score -= min(penalty, 24)
    parsed["score"] = max(0, min(100, score))
    return parsed


def score_job(job: dict) -> dict:
    """Score a single job against the configured profile using Claude Haiku."""
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    combined_text = f"{title} {description}"

    prompt = f"""
You are evaluating job relevance for a candidate profile.

Candidate profile:
{json.dumps(PROFILE, indent=2)}

Job listing:
{json.dumps(job, indent=2)}

Return VALID JSON ONLY with exactly this schema:
{{
  "score": number,
  "why_fit": string,
  "best_angle": string,
  "gaps": string
}}

Rules:
- score must be 0-100
- Keep why_fit concise and specific
- best_angle should be the strongest positioning angle
- gaps should be honest but brief
- Do not include markdown, code fences, or any extra keys
""".strip()

    try:
        response_text = call_claude_haiku(prompt)
        payload = _extract_json_payload(response_text)
        parsed = json.loads(payload)

        required_keys = {"score", "why_fit", "best_angle", "gaps"}
        if not required_keys.issubset(parsed):
            return DEFAULT_SCORE

        return _apply_boosts(parsed, combined_text)
    except Exception as e:
        print("❌ CLAUDE SCORING ERROR:", str(e))
        return DEFAULT_SCORE


def score_jobs_batch(jobs: list[dict]) -> list[dict]:
    """
    Score all jobs using chunked Claude Haiku calls.
    Sends jobs in chunks of 8 instead of one call per job.
    Falls back to individual scoring for any chunk that fails.
    """
    if not jobs:
        return []

    CHUNK_SIZE = 8
    all_results = []
    chunks = [jobs[i:i + CHUNK_SIZE] for i in range(0, len(jobs), CHUNK_SIZE)]

    print(f"📦 Scoring {len(jobs)} jobs in {len(chunks)} chunks of up to {CHUNK_SIZE}")

    for chunk_index, chunk in enumerate(chunks):
        jobs_payload = [
            {"index": i, "job": job}
            for i, job in enumerate(chunk)
        ]

        prompt = f"""
You are evaluating job relevance for a candidate profile.

Candidate profile:
{json.dumps(PROFILE, indent=2)}

Below are {len(chunk)} job listings. Score each one and return a JSON array with exactly {len(chunk)} objects in the same order as the input.

Each object must have exactly these keys:
{{
  "score": number (0-100),
  "why_fit": string,
  "best_angle": string,
  "gaps": string
}}

Jobs:
{json.dumps(jobs_payload, indent=2)}

Return ONLY a valid JSON array. No markdown, no code fences, no preamble, no extra keys.
""".strip()

        try:
            response_text = call_claude_haiku(prompt)
            payload = _extract_json_payload(response_text)
            parsed_list = json.loads(payload)

            if not isinstance(parsed_list, list) or len(parsed_list) != len(chunk):
                raise ValueError(f"Expected {len(chunk)} results, got {len(parsed_list) if isinstance(parsed_list, list) else 'non-list'}")

            required_keys = {"score", "why_fit", "best_angle", "gaps"}
            for i, (job, parsed) in enumerate(zip(chunk, parsed_list)):
                if not required_keys.issubset(parsed):
                    print(f"⚠️ Chunk {chunk_index} job {i} missing keys, using default score")
                    all_results.append(DEFAULT_SCORE)
                    continue
                combined_text = f"{(job.get('title') or '').lower()} {(job.get('description') or '').lower()}"
                all_results.append(_apply_boosts(parsed, combined_text))

            print(f"✅ Chunk {chunk_index + 1}/{len(chunks)} scored ({len(chunk)} jobs)")

        except Exception as e:
            print(f"⚠️ Chunk {chunk_index + 1} failed ({e}), falling back to individual scoring for this chunk")
            for job in chunk:
                all_results.append(score_job(job))

    print(f"✅ Batch complete: scored {len(all_results)} jobs in {len(chunks)} Claude calls")
    return all_results
