"""Local fallback config — used only for --mock --dry-run when DATABASE_URL is not set.
Real user profiles are always loaded from Postgres via get_user_config(user_id).
"""

PROFILE = {
    "name": "Test User",
    "roles": ["Professional"],
    "location": "Remote",
    "constraints": "",
    "summary": "Experienced professional seeking new opportunities.",
}

KEYWORDS = [
    "job openings",
    "hiring now",
    "full time position",
]
