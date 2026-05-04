import requests


def fetch_lever_boards(companies):
    jobs = []

    for company in companies:
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception:
            continue

        for job in data:
            description = job.get("description") or ""
            jobs.append(
                {
                    "company": company,
                    "title": job.get("text"),
                    "location": job.get("categories", {}).get("location"),
                    "salary": None,
                    "description": description[:4000],
                    "url": job.get("hostedUrl"),
                    "source": "lever",
                }
            )

    return jobs
