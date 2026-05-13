"""Mock job source for local pipeline testing.
Jobs are intentionally neutral — they test pipeline mechanics (APPLY/REVIEW/SKIP paths),
not any specific profession. Real job relevance is determined by Claude against each
user's uploaded profile.
"""


def get_jobs() -> list[dict]:
    return [
        {
            "company": "Mock Company A",
            "title": "Mock Role A",
            "location": "Remote",
            "salary": "$80,000 - $100,000",
            "description": "Mock job listing for pipeline testing. High fit score.",
            "url": "https://example.com/job-a",
            "source": "mock",
            "mock_score": 92,
        },
        {
            "company": "Mock Company B",
            "title": "Mock Role B",
            "location": "Remote",
            "salary": "$70,000 - $90,000",
            "description": "Mock job listing for pipeline testing. Medium fit score.",
            "url": "https://example.com/job-b",
            "source": "mock",
            "mock_score": 76,
        },
        {
            "company": "Mock Company C",
            "title": "Mock Role C",
            "location": "Remote",
            "salary": "$60,000 - $75,000",
            "description": "Mock job listing for pipeline testing. Low fit score.",
            "url": "https://example.com/job-c",
            "source": "mock",
            "mock_score": 55,
        },
    ]
