_ALLOWED_CITY_KEYWORDS = [
    "new york", "nyc", "ny,", ", ny",
    "new jersey", "nj,", ", nj",
    "north carolina", "nc,", ", nc",
    "charlotte", "raleigh", "durham",
]

_DISALLOWED_LOCATIONS = ["tokyo", "seoul", "london"]


def _location_is_allowed(location: str) -> bool:
    """
    Remote is always allowed regardless of city.
    Hybrid passes only when no city is specified (no comma in string) or
    when the city is in the allowed list — "Hybrid (Los Angeles, CA)" fails.
    Allowed city keywords pass unconditionally.
    Empty/unknown location passes.
    """
    if not location:
        return True
    loc = location.lower()
    if "remote" in loc or "anywhere" in loc:
        return True
    if any(k in loc for k in _ALLOWED_CITY_KEYWORDS):
        return True
    # "Hybrid" with no comma means no "City, State" is specified → pass
    if "hybrid" in loc and "," not in loc:
        return True
    return False


def disqualify_jobs(jobs: list[dict]) -> list[dict]:
    """
    Remove jobs that are clearly not worth scoring.
    Hard filters BEFORE scoring.
    """
    filtered = []

    for job in jobs:
        title = (job.get("title") or "").lower()
        description = (job.get("description") or "").lower()

        # --- DISQUALIFY: Non-AI / irrelevant roles ---
        non_ai_keywords = [
            "supply chain",
            "mechanical",
            "civil engineer",
            "construction",
            "hardware technician",
            "it support",
            "network engineer",
        ]
        if any(k in title for k in non_ai_keywords):
            print(f"Disqualified: {job.get('title')}")
            continue

        # --- DISQUALIFY: Research-heavy roles ---
        research_keywords = [
            "research scientist",
            "research fellow",
            "postdoctoral",
            "phd required",
            "ph.d",
            "faculty",
        ]
        if any(k in title for k in research_keywords):
            print(f"Disqualified: {job.get('title')}")
            continue

        # --- DISQUALIFY: Fellowships / internships ---
        if "fellow" in title or "intern" in title:
            print(f"Disqualified: {job.get('title')}")
            continue

        # --- DISQUALIFY: Explicit academic requirements ---
        if "phd" in description or "ph.d" in description:
            print(f"Disqualified: {job.get('title')}")
            continue

        filtered.append(job)

    return filtered


def passes_filters(job: dict) -> bool:
    """
    Soft filter — allow most relevant AI jobs through.
    Only block obvious mismatches.
    """
    title = (job.get("title") or "").lower()

    block_keywords = [
        "machine learning engineer",
        "machine learning scientist",
        "data scientist",
        "research scientist",
        "research engineer",
        "deep learning",
        "computer vision",
        "phd",
        "postdoctoral",
        "statistician",
        "quantitative researcher",
        "ml research",
        "theoretical",
    ]
    if any(k in title for k in block_keywords):
        return False

    # --- REQUIRE: Must be AI/tech related ---
    relevant_keywords = [
        "ai",
        "llm",
        "prompt",
        "agent",
        "automation",
        "applied ai",
        "systems",
        "integrations",
        "generative ai",
        "solutions engineer",
        "architect",
        "developer",
        "engineer",
        "creative technologist",
    ]

    if not any(k in title for k in relevant_keywords):
        return False

    # --- LOCATION FILTER: Only allow remote, hybrid w/ allowed city, or known city ---
    location = (job.get("location") or "").lower()
    if not _location_is_allowed(location):
        print(f"Location filtered ({job.get('location')}): {job.get('title')}")
        return False

    return True


def qualifies_for_apply(job: dict) -> bool:
    """
    Final sanity check AFTER scoring.
    Prevents applying to jobs that are not realistic.
    """

    title = (job.get("title") or "").lower()
    location = (job.get("location") or "").lower()

    # --- LOCATION FILTER ---
    relocation_only_markers = ["relocation required", "visa unavailable", "on-site only"]
    for marker in relocation_only_markers:
        if marker in location:
            print(f"Location blocked ({marker}): {job.get('title')} at {job.get('company')}")
            return False

    for blocked in _DISALLOWED_LOCATIONS:
        if blocked in location:
            print(f"Location blocked ({blocked}): {job.get('title')} at {job.get('company')}")
            return False

    if not _location_is_allowed(location):
        print(f"Location not in allowed list ({job.get('location')}): {job.get('title')} at {job.get('company')}")
        return False

    # --- SENIORITY FILTER ---
    senior_keywords = ["senior", "staff", "principal", "lead", "manager"]
    if any(k in title for k in senior_keywords):
        return False

    # --- ROLE TYPE FILTER ---
    bad_roles = [
        "evangelist",
        "marketing",
        "sales",
        "recruiter",
    ]
    if any(k in title for k in bad_roles):
        return False

    return True
