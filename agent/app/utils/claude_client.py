"""Shared Claude API client utilities with per-run token tracking."""

from __future__ import annotations

import os
import threading
import time

from anthropic import Anthropic
from dotenv import load_dotenv


load_dotenv()

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

# Pricing per million tokens
_HAIKU_COST = {"input": 0.80, "output": 4.00}
_SONNET_COST = {"input": 3.00, "output": 15.00}

_RETRY_DELAYS = [2, 4]

_token_store = threading.local()


def reset_token_counts() -> None:
    """Call once at the start of each pipeline run."""
    _token_store.haiku_input = 0
    _token_store.haiku_output = 0
    _token_store.sonnet_input = 0
    _token_store.sonnet_output = 0


def get_token_counts() -> dict:
    """Return accumulated token counts and estimated cost for the current run."""
    hi = getattr(_token_store, "haiku_input", 0)
    ho = getattr(_token_store, "haiku_output", 0)
    si = getattr(_token_store, "sonnet_input", 0)
    so = getattr(_token_store, "sonnet_output", 0)
    cost = (
        (hi * _HAIKU_COST["input"] + ho * _HAIKU_COST["output"]) / 1_000_000
        + (si * _SONNET_COST["input"] + so * _SONNET_COST["output"]) / 1_000_000
    )
    return {
        "haiku_tokens": hi + ho,
        "sonnet_tokens": si + so,
        "estimated_cost": round(cost, 4),
    }


def _call(prompt: str, model: str) -> str:
    """Core Claude call with exponential backoff — 3 attempts, waits 2s then 4s."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set.")

    client = Anthropic(api_key=api_key)
    last_error: Exception | None = None

    for attempt in range(1, len(_RETRY_DELAYS) + 2):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1500,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )

            # Accumulate token usage for this run
            usage = response.usage
            if model == HAIKU_MODEL:
                _token_store.haiku_input = getattr(_token_store, "haiku_input", 0) + usage.input_tokens
                _token_store.haiku_output = getattr(_token_store, "haiku_output", 0) + usage.output_tokens
            elif model == SONNET_MODEL:
                _token_store.sonnet_input = getattr(_token_store, "sonnet_input", 0) + usage.input_tokens
                _token_store.sonnet_output = getattr(_token_store, "sonnet_output", 0) + usage.output_tokens

            parts = []
            for block in response.content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)

            response_text = "\n".join(parts).strip()

            if not response_text:
                raise ValueError("Claude returned empty response")

            return response_text

        except Exception as e:
            last_error = e
            if attempt <= len(_RETRY_DELAYS):
                delay = _RETRY_DELAYS[attempt - 1]
                print(f"⚠️ Claude attempt {attempt}/{len(_RETRY_DELAYS) + 1} failed ({e}) — retrying in {delay}s")
                time.sleep(delay)
            else:
                print(f"❌ Claude failed after {len(_RETRY_DELAYS) + 1} attempts: {e}")

    raise last_error  # type: ignore[misc]


def call_claude_haiku(prompt: str) -> str:
    """Send a prompt to Claude Haiku. Use for scoring and cheap tasks."""
    return _call(prompt, HAIKU_MODEL)


def call_claude_sonnet(prompt: str) -> str:
    """Send a prompt to Claude Sonnet. Use for cover letters and quality tasks."""
    return _call(prompt, SONNET_MODEL)


def call_claude(prompt: str) -> str:
    """Alias for call_claude_haiku. Kept for backwards compatibility."""
    return call_claude_haiku(prompt)


def parse_resume_with_claude(resume_text: str, interview_answers: str = "") -> dict:
    """Extract structured profile fields from resume + optional interview answers."""
    import json
    import re

    interview_section = ""
    if interview_answers.strip():
        interview_section = f"""
The candidate also answered these questions about what they're looking for:
{interview_answers.strip()}

Use their answers to make keywords and target_roles reflect their INTENT, not just their history.
"""

    prompt = f"""Extract structured profile data and return ONLY valid JSON — no markdown, no explanation.

Required JSON shape:
{{
  "name": "Full Name",
  "target_roles": ["Job Title 1", "Job Title 2"],
  "location_pref": "City, State or Remote",
  "summary": "2-3 sentence professional summary",
  "constraints": "Any constraints like no relocation, part-time only. Empty string if none.",
  "keywords": ["keyword1", "keyword2"]
}}

Rules:
- target_roles: 3-5 job titles the candidate would be a strong fit for
- keywords: 5-10 specific job search terms (skills, industries, role types)
- summary: written in third person, concise
- Prioritize what they WANT over what they've done if interview answers conflict with resume history
{interview_section}
Resume:
{resume_text}"""

    response = _call(prompt, HAIKU_MODEL)
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", response).strip()
    return json.loads(cleaned)
