import os
import re
import requests
from serpapi import GoogleSearch


def fetch_google_jobs(keyword, location_pref=""):
    api_key = os.getenv("SERPAPI_API_KEY")

    if not api_key:
        print("❌ SERPAPI_API_KEY not set")
        return []

    q = keyword
    if location_pref.lower() == "remote":
        q = f"{keyword} remote"

    params = {
        "engine": "google_jobs",
        "q": q,
        "hl": "en",
        "num": 20,
        "api_key": api_key,
    }

    if location_pref and location_pref.lower() != "remote":
        params["location"] = location_pref

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


def fetch_jsearch_jobs(keyword, location_pref=""):
    api_key = os.getenv("JSEARCH_API_KEY")
    if not api_key:
        return []

    query = keyword
    if location_pref and location_pref.lower() != "remote":
        query = f"{keyword} jobs in {location_pref}"
    elif location_pref and location_pref.lower() == "remote":
        query = f"{keyword} remote jobs"

    try:
        response = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "x-rapidapi-host": "jsearch.p.rapidapi.com",
                "x-rapidapi-key": api_key,
            },
            params={"query": query, "num_pages": "1", "country": "us", "date_posted": "all"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ JSearch error for '{keyword}': {e}")
        return []

    job_list = data.get("data", [])
    if not isinstance(job_list, list):
        print(f"❌ JSearch: unexpected response shape for '{keyword}'")
        return []

    jobs = []
    for job in job_list:
        if not isinstance(job, dict):
            continue
        location_parts = [job.get("job_city"), job.get("job_state")]
        location = ", ".join(p for p in location_parts if p) or job.get("job_country")

        salary = None
        sal_min = job.get("job_min_salary")
        sal_max = job.get("job_max_salary")
        if sal_min and sal_max:
            salary = f"${sal_min:,.0f} – ${sal_max:,.0f}"

        jobs.append({
            "company": job.get("employer_name"),
            "title": job.get("job_title"),
            "location": location,
            "salary": salary,
            "description": job.get("job_description") or "",
            "url": job.get("job_apply_link") or job.get("job_google_link"),
            "source": "jsearch",
        })

    return jobs


def fetch_adzuna_jobs(keyword, location_pref=""):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 20,
        "what": keyword,
    }
    if location_pref and location_pref.lower() != "remote":
        params["where"] = location_pref

    try:
        response = requests.get(
            "https://api.adzuna.com/v1/api/jobs/us/search/1",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Adzuna error for '{keyword}': {e}")
        return []

    result_list = data.get("results", [])
    if not isinstance(result_list, list):
        print(f"❌ Adzuna: unexpected response shape for '{keyword}'")
        return []

    jobs = []
    for job in result_list:
        if not isinstance(job, dict):
            continue
        sal_min = job.get("salary_min")
        sal_max = job.get("salary_max")
        salary = f"${sal_min:,.0f} – ${sal_max:,.0f}" if sal_min and sal_max else None

        jobs.append({
            "company": (job.get("company") or {}).get("display_name"),
            "title": job.get("title"),
            "location": (job.get("location") or {}).get("display_name"),
            "salary": salary,
            "description": job.get("description") or "",
            "url": job.get("redirect_url"),
            "source": "adzuna",
        })

    return jobs


def fetch_the_muse_jobs():
    api_key = os.getenv("THE_MUSE_API_KEY")
    if not api_key:
        return []

    try:
        response = requests.get(
            "https://www.themuse.com/api/public/jobs",
            params={"api_key": api_key, "page": 0, "level": "Mid Level,Senior Level,Entry Level"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ The Muse error: {e}")
        return []

    result_list = data.get("results", [])
    if not isinstance(result_list, list):
        print("❌ The Muse: unexpected response shape")
        return []

    jobs = []
    for job in result_list:
        if not isinstance(job, dict):
            continue
        locations = job.get("locations", [])
        location = locations[0].get("name") if locations else None
        description = re.sub(r"<[^>]+>", " ", job.get("contents") or "").strip()[:2000]

        jobs.append({
            "company": (job.get("company") or {}).get("name"),
            "title": job.get("name"),
            "location": location,
            "salary": None,
            "description": description,
            "url": (job.get("refs") or {}).get("landing_page"),
            "source": "the_muse",
        })

    return jobs


def fetch_all_jobs(keywords: list[str], location_pref: str = "") -> list:
    jobs = []

    print("🌍 GLOBAL JOB SEARCH START")

    for keyword in keywords:
        # Primary: SerpAPI → Serper fallback
        serpapi_jobs = fetch_google_jobs(keyword, location_pref=location_pref)
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

        # Supplementary: JSearch (RapidAPI — aggregates Indeed, LinkedIn, Glassdoor)
        jsearch_jobs = fetch_jsearch_jobs(keyword, location_pref=location_pref)
        if jsearch_jobs:
            print(f"JSearch: {len(jsearch_jobs)} jobs for '{keyword}'")
            jobs.extend(jsearch_jobs)

        # Supplementary: Adzuna
        adzuna_jobs = fetch_adzuna_jobs(keyword, location_pref=location_pref)
        if adzuna_jobs:
            print(f"Adzuna: {len(adzuna_jobs)} jobs for '{keyword}'")
            jobs.extend(adzuna_jobs)

    # The Muse: run once per pipeline (category-based, not keyword-searchable)
    muse_jobs = fetch_the_muse_jobs()
    if muse_jobs:
        print(f"The Muse: {len(muse_jobs)} jobs")
        jobs.extend(muse_jobs)

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
