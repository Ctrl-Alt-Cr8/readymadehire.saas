"""Shared Claude API client utilities."""

from __future__ import annotations

import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv


load_dotenv()

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-20250514"

_RETRY_DELAYS = [2, 4]  # seconds before attempt 2 and attempt 3


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
