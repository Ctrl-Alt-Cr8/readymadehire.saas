"""Cover letter composition powered by Claude."""

from __future__ import annotations

import json
import re

from rich.console import Console

from app.utils.claude_client import call_claude_sonnet


console = Console()


RETRY_PREFIX = (
    "IMPORTANT: The previous response did not meet strict formatting and style "
    "requirements. You MUST follow ALL constraints exactly, including paragraph "
    "structure, banned phrases, and ending format."
)


def _build_cover_letter_prompt(job: dict, profile: dict) -> str:
    """Build the base prompt for cover letter generation."""
    return f"""
Write a tailored cover letter for this job using a high-signal, professional voice.

Candidate profile:
{json.dumps(profile, indent=2)}

Job:
{json.dumps(job, indent=2)}

Your objective:
- Position the candidate based on their background, target roles, and professional expertise.
- Write with confidence and specificity, demonstrating their experience.
- Write like a peer speaking to decision-makers, not like a junior applicant.

Tone and voice requirements:
- Confident, direct, peer-to-peer.
- No corporate fluff.
- No exaggerated claims (for example: "I've spent my career...").
- Prefer grounded phrasing patterns such as:
  - "I've been building..."
  - "My work focuses on..."
  - "I specialize in..."

Mandatory structure (exactly 5 paragraphs):
1) Opening:
    - Strong, specific opening that immediately establishes the candidate's professional focus.
    - Avoid generic openers. Start with what makes them distinct.
2) Relevance:
    - Reference something specific about this role or company.
    - Show awareness of what they are building or trying to accomplish.
    - Avoid generic statements.
3) Proof:
    - Highlight concrete experience and achievements relevant to the role.
    - Be specific — show impact, not just responsibilities.
4) Positioning:
    - Show alignment with what the company is trying to accomplish.
    - Speak as a peer with relevant expertise, not as a junior applicant.
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
- Do NOT explain basic concepts in the field. Assume the reader is knowledgeable.

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
{profile['name']}

- Output plain text only.
- Return only the final cover letter text.
- Output must read like a real human wrote it, demonstrate capability through specificity, and position the candidate as a professional, not an applicant.
""".strip()


def validate_cover_letter(text: str, profile: dict) -> dict:
    """Validate key formatting and style constraints for generated cover letters."""
    issues: list[str] = []
    normalized_text = text.strip()

    required_ending = f"Best,\n{profile['name']}"
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


def generate_cover_letter(job: dict, profile: dict) -> dict:
    """Generate a tailored cover letter. Returns {"text": str, "valid": bool, "issues": list[str]}."""
    base_prompt = _build_cover_letter_prompt(job, profile)

    first_attempt = call_claude_sonnet(base_prompt).strip()
    if validate_cover_letter(first_attempt, profile).get("valid", False):
        return {"text": first_attempt, "valid": True, "issues": []}

    retry_prompt = f"{RETRY_PREFIX}\n\n{base_prompt}"
    second_attempt = call_claude_sonnet(retry_prompt).strip()
    second_validation = validate_cover_letter(second_attempt, profile)

    return {
        "text": second_attempt,
        "valid": second_validation["valid"],
        "issues": second_validation.get("issues", []),
    }
