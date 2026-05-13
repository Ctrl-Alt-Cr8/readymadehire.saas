from __future__ import annotations


def _location_is_allowed(location: str, location_pref: str = "") -> bool:
    if not location:
        return True
    loc = location.lower()
    pref = location_pref.lower().strip() if location_pref else ""

    if "remote" in loc or "anywhere" in loc:
        return True

    # User wants remote only — block anything that isn't remote
    if pref == "remote":
        return False

    # User has a specific location — check for keyword match
    if pref:
        pref_keywords = [k.strip() for k in pref.replace("/", ",").split(",") if k.strip()]
        if any(k in loc for k in pref_keywords):
            return True
        # "Hybrid" with no city specified (no comma) — pass through
        if "hybrid" in loc and "," not in loc:
            return True
        return False

    # No preference set — allow everything
    return True


def disqualify_jobs(jobs: list[dict], config=None) -> list[dict]:
    """Hard-block universally irrelevant listings before scoring."""
    filtered = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        title = (job.get("title") or "").lower()
        description = (job.get("description") or "").lower()

        # Internships — universally low-relevance for adults using a job agent
        if "intern" in title and "internal" not in title:
            print(f"Disqualified (internship): {job.get('title')}")
            continue

        # Hard PhD requirement — most users won't qualify
        if "phd required" in description or "ph.d. required" in description:
            print(f"Disqualified (PhD required): {job.get('title')}")
            continue

        filtered.append(job)

    return filtered


def passes_filters(job: dict, config=None) -> bool:
    """
    Relevance and location filter.
    Relevance is driven by the user's target_roles — no hardcoded profession assumptions.
    Claude scoring handles fine-grained fit; this just drops obvious title mismatches.
    """
    title = (job.get("title") or "").lower()

    # Build relevance keywords from user's target roles
    if config and config.target_roles:
        skip_words = {"and", "the", "for", "with", "via", "of", "in", "at", "to", "or", "a"}
        role_words = set()
        for role in config.target_roles:
            for word in role.lower().split():
                if len(word) > 3 and word not in skip_words:
                    role_words.add(word)
        if role_words and not any(word in title for word in role_words):
            return False

    # Location filter using user's preference
    location_pref = (config.location_pref if config else "") or ""
    if not _location_is_allowed(job.get("location") or "", location_pref):
        print(f"Location filtered ({job.get('location')}): {job.get('title')}")
        return False

    return True


def qualifies_for_apply(job: dict) -> bool:
    """
    Final gate after scoring.
    Claude handles fit — this function is intentionally minimal.
    Only blocks if the application itself is impossible (not just a bad fit).
    """
    return True
