"""Cover letter composition powered by Claude."""

from __future__ import annotations

import json
import re

from rich.console import Console

from app.config import PROFILE
from app.utils.claude_client import call_claude_sonnet


console = Console()


RETRY_PREFIX = (
    "IMPORTANT: The previous response did not meet strict formatting and style "
    "requirements. You MUST follow ALL constraints exactly, including paragraph "
    "structure, banned phrases, and ending format."
)


def _build_cover_letter_prompt(job: dict) -> str:
    """Build the base prompt for cover letter generation."""
    return f"""
Write a tailored cover letter for this job using a high-signal, builder-focused voice.

Candidate profile:
{json.dumps(PROFILE, indent=2)}

Job:
{json.dumps(job, indent=2)}

Your objective:
- Position the candidate as an AI systems builder, not a traditional applicant.
- Write like a peer speaking to builders.

Tone and voice requirements:
- Confident, direct, peer-to-peer.
- No corporate fluff.
- No exaggerated claims (for example: "I've spent my career...").
- Prefer grounded phrasing patterns such as:
  - "I've been building..."
  - "My work focuses on..."
  - "I build..."

Mandatory structure (exactly 5 paragraphs):
1) Opening:
    - Pattern-interrupt style opening.
    - Example style: "Most AI systems stop at generation. I focus on systems that act and actually ship."
2) Relevance:
    - Reference something specific about this role or company.
    - Show awareness of what they are building.
    - Avoid generic statements.
3) Proof:
    - Highlight concrete system-building experience.
    - Must include evidence across LLM orchestration, AI agents, production deployment, and reliability / edge cases.
4) Positioning:
    - Show alignment with what the company is trying to build.
    - Speak as a peer, not a junior applicant.
    - No begging language and no "fit" language.
5) Close:
    - Short, confident close.
    - No fluff, no begging language.

Strict prohibitions:
- Do NOT mention salary, compensation, or pay.
- Do NOT mention remote/hybrid preferences.
- Do NOT mention availability logistics.
- Do NOT mention "this works for me".
- Do NOT use these phrases:
  - "I'm excited to apply"
  - "I believe I'm a great fit"
  - "I am passionate about"
  - "hardworking"
  - "team player"
  - "This role works for me"
- Do NOT explain basic AI concepts. Assume the reader is technical.

Readymade.AI rule:
- Mention Readymade.AI only if it is clearly relevant to the role context.
- Use it as proof of system-building capability when included.
- Do not force it into every letter.

Style constraints:
- Avoid excessive em dashes.
- Maximum 1 em dash in the entire letter.
- Prefer shorter sentences with periods or commas.
- Vary sentence structure to avoid repetitive rhythm.
- Keep writing natural and human.

Length and output:
- 180 to 250 words total.
- Exactly 5 paragraphs, separated by blank lines.
- Keep paragraphs tight and readable; no rambling.
- End with this exact sign-off block:

Best,
{PROFILE['name']}

- Output plain text only.
- Return only the final cover letter text.
- Output must read like a real human wrote it, demonstrate capability through specificity, and position the candidate as a builder, not an applicant.
""".strip()


def validate_cover_letter(text: str) -> dict:
    """Validate key formatting and style constraints for generated cover letters."""
    issues: list[str] = []
    normalized_text = text.strip()

    required_ending = f"Best,\n{PROFILE['name']}"
    if not normalized_text.endswith(required_ending):
        issues.append("Missing required ending format")

    banned_phrases = [
        "i'm excited to apply",
        "i believe i'm a great fit",
        "i am passionate about",
        "hardworking",
        "team player",
        "this role works for me",
        "this works for me",
    ]
    lowered = normalized_text.lower()
    for phrase in banned_phrases:
        if phrase in lowered:
            issues.append(f"Contains banned phrase: {phrase}")

    banned_topics = [
        r"\bsalary\b",
        r"\bcompensation\b",
        r"\bpay\b",
        r"\bremote\b",
        r"\bhybrid\b",
        r"\bavailability\b",
    ]
    for pattern in banned_topics:
        if re.search(pattern, lowered):
            issues.append(f"Contains prohibited topic: {pattern}")
            break

    if normalized_text.count("—") > 1:
        issues.append("Uses more than one em dash")

    words = re.findall(r"\b\w+[\w'\.-]*\b", normalized_text)
    if len(words) < 180 or len(words) > 250:
        issues.append("Word count is outside 180-250")

    body_text = normalized_text
    if body_text.endswith(required_ending):
        body_text = body_text[: -len(required_ending)].rstrip()
    paragraphs = [part for part in re.split(r"\n\s*\n", body_text) if part.strip()]
    if len(paragraphs) != 5:
        issues.append("Does not contain exactly 5 body paragraphs")

    return {"valid": len(issues) == 0, "issues": issues}


def generate_cover_letter(job: dict) -> dict:
    """Generate a tailored cover letter. Returns {"text": str, "valid": bool, "issues": list[str]}."""
    base_prompt = _build_cover_letter_prompt(job)

    first_attempt = call_claude_sonnet(base_prompt).strip()
    if validate_cover_letter(first_attempt).get("valid", False):
        return {"text": first_attempt, "valid": True, "issues": []}

    retry_prompt = f"{RETRY_PREFIX}\n\n{base_prompt}"
    second_attempt = call_claude_sonnet(retry_prompt).strip()
    second_validation = validate_cover_letter(second_attempt)

    return {
        "text": second_attempt,
        "valid": second_validation["valid"],
        "issues": second_validation.get("issues", []),
    }
