import os
import requests
from serpapi import GoogleSearch


def fetch_google_jobs(keyword):
    api_key = os.getenv("SERPAPI_API_KEY")

    if not api_key:
        print("❌ SERPAPI_API_KEY not set")
        return []

    params = {
        "engine": "google_jobs",
        "q": keyword,
        "hl": "en",
        "api_key": api_key
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        print(f"❌ SerpAPI error for '{keyword}': {e}")
        return []

    jobs = []

    for job in results.get("jobs_results", []):
        # Try to get direct link first, fall back to Google Jobs search URL
        direct_url = (
            job.get("related_links", [{}])[0].get("link")
            if job.get("related_links")
            else None
        )
        if not direct_url:
            title = job.get("title", "")
            company = job.get("company_name", "")
            query = f"{title} {company}".strip().replace(" ", "+")
            direct_url = f"https://www.google.com/search?q={query}&ibp=htl;jobs"

        jobs.append({
            "company": job.get("company_name"),
            "title": job.get("title"),
            "location": job.get("location"),
            "salary": (job.get("detected_extensions") or {}).get("salary"),
            "description": job.get("description") or "",
            "url": direct_url,
            "source": "google_jobs",
        })

    return jobs


def fetch_serper_jobs(keyword):
    api_key = os.getenv("SERPER_API_KEY")

    if not api_key:
        print("❌ SERPER_API_KEY not set")
        return []

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": f"{keyword} jobs"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Serper.dev error for '{keyword}': {e}")
        return []

    jobs = []

    for result in data.get("organic", []):
        jobs.append({
            "company": None,
            "title": result.get("title"),
            "location": None,
            "salary": None,
            "description": result.get("snippet") or "",
            "url": result.get("link"),
            "source": "serper",
        })

    return jobs


KEYWORDS = [
    "ai agent engineer",
    "prompt engineer",
    "llm engineer",
    "ai automation engineer",
    "generative ai engineer",
    "applied ai engineer",
    "creative technologist ai",
    "founding ai engineer",
]


def fetch_all_jobs():
    jobs = []

    print("🌍 GLOBAL JOB SEARCH START")

    for keyword in KEYWORDS:
        serpapi_jobs = fetch_google_jobs(keyword)
        if serpapi_jobs:
            print(f"SerpAPI: {len(serpapi_jobs)} jobs for '{keyword}'")
            jobs.extend(serpapi_jobs)
        else:
            print(f"SerpAPI: no results for '{keyword}' — trying Serper.dev")
            serper_jobs = fetch_serper_jobs(keyword)
            if serper_jobs:
                print(f"Serper.dev: {len(serper_jobs)} jobs for '{keyword}'")
            else:
                print(f"Serper.dev: no results for '{keyword}'")
            jobs.extend(serper_jobs)

    print(f"Total jobs collected: {len(jobs)}")

    # 🔧 SECONDARY: fallback structured sources (disabled — causes hangs, re-enable later)
    # try:
    #     gh_jobs = fetch_greenhouse_boards([
    #         "openai",
    #         "anthropic",
    #         "scaleai",
    #         "perplexityai",
    #         "runway",
    #         "huggingface",
    #         "cohere"
    #     ])
    #     print(f"Greenhouse jobs: {len(gh_jobs)}")
    #     jobs.extend(gh_jobs)
    # except Exception as e:
    #     print(f"❌ Greenhouse error: {e}")

    # try:
    #     lever_jobs = fetch_lever_boards([
    #         "vercel",
    #         "notion",
    #         "figma"
    #     ])
    #     print(f"Lever jobs: {len(lever_jobs)}")
    #     jobs.extend(lever_jobs)
    # except Exception as e:
    #     print(f"❌ Lever error: {e}")

    # Deduplicate by title+company (case-insensitive)
    seen_keys = set()
    deduped_jobs = []
    for job in jobs:
        title = (job.get("title") or "").lower().strip()
        company = (job.get("company") or "").lower().strip()
        key = f"{title}|{company}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_jobs.append(job)
    print(f"After deduplication: {len(deduped_jobs)} jobs")
    return deduped_jobs
