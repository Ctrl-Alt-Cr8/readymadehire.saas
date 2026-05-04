import requests


def fetch_greenhouse_boards(boards):
    jobs = []

    for board in boards:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception:
            continue

        for job in data.get("jobs", []):
            jobs.append(
                {
                    "company": board,
                    "title": job.get("title"),
                    "location": job.get("location", {}).get("name"),
                    "salary": None,
                    "description": (job.get("content") or "")[:4000],
                    "url": job.get("absolute_url"),
                    "source": "greenhouse",
                }
            )

    return jobs
