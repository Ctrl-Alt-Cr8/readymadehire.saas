"""CLI entrypoint for the job-agent pipeline."""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
import re

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.composer.cover_letter import generate_cover_letter
from app.scoring.filters import disqualify_jobs, passes_filters, qualifies_for_apply
from app.scoring.scorer import score_job, score_jobs_batch
from app.sources.fetcher_router import fetch_all_jobs
from app.sources.mock_jobs import get_jobs as get_mock_jobs
from app.storage.job_store import init_db, is_known_job, record_job, update_last_seen
from app.utils.send_email import send_email


console = Console()

RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "")

APPLY_THRESHOLD = 88
REVIEW_THRESHOLD = 70


def _sanitize_filename_part(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9\s_-]", "", value.lower())
    sanitized = re.sub(r"\s+", "_", sanitized).strip("_")
    return sanitized or "unknown"


def _cover_letter_filename(company: str, role: str) -> str:
    return f"{_sanitize_filename_part(company)}_{_sanitize_filename_part(role)}.txt"


def safe_ascii(text: str) -> str:
    return (
        str(text)
        .replace("\xa0", " ")
        .replace("\u2014", "-")
        .encode("ascii", "ignore")
        .decode()
    )


def run(mock: bool = False, dry_run: bool = False, user_id: str = "") -> None:
    """Fetch jobs, score fit, and generate tailored cover letters."""
    if not user_id:
        user_id = os.getenv("USER_ID", "default")

    output_dir = "outputs"
    cover_letters_dir = os.path.join(output_dir, "cover_letters")
    os.makedirs(cover_letters_dir, exist_ok=True)

    init_db()

    if mock:
        jobs = get_mock_jobs()
        print(f"[MOCK] Loaded {len(jobs)} mock jobs")
    else:
        jobs = fetch_all_jobs()
        print(f"Fetched {len(jobs)} jobs")

    jobs = disqualify_jobs(jobs)
    print(f"After disqualification: {len(jobs)} jobs")

    jobs = [job for job in jobs if passes_filters(job)]
    print(f"After filtering: {len(jobs)} jobs")

    new_jobs = []
    skipped_known = 0
    for job in jobs:
        if is_known_job(job.get("title", ""), job.get("company", ""), user_id=user_id):
            if not dry_run:
                update_last_seen(job.get("title", ""), job.get("company", ""), user_id=user_id)
            skipped_known += 1
        else:
            new_jobs.append(job)
    if skipped_known:
        print(f"Skipped {skipped_known} already-seen job(s)")
    jobs = new_jobs
    print(f"After memory filter: {len(jobs)} new job(s)")

    # Cap at 50 jobs before scoring to control Claude API costs
    MAX_JOBS_TO_SCORE = 50
    if len(jobs) > MAX_JOBS_TO_SCORE:
        jobs = jobs[:MAX_JOBS_TO_SCORE]
        print(f"Capped to {MAX_JOBS_TO_SCORE} jobs for scoring")

    if mock or dry_run:
        mode = "MOCK + DRY RUN" if (mock and dry_run) else "MOCK" if mock else "DRY RUN"
        print(f"Mode: {mode}")
    console.print("[bold cyan]job-agent[/bold cyan] • Starting pipeline\n")

    scored_jobs: list[dict[str, object]] = []
    if mock and dry_run:
        for job in jobs:
            scored_jobs.append({
                "job": job,
                "score": {
                    "score": job.get("mock_score", 75),
                    "why_fit": "[mock — no Claude call]",
                    "best_angle": "[mock — no Claude call]",
                    "gaps": "[mock — no Claude call]",
                },
            })
        print(f"[DRY RUN] Using mock scores for {len(jobs)} jobs (no Claude call)")
    else:
        try:
            scores = score_jobs_batch(jobs)
            for job, score in zip(jobs, scores):
                scored_jobs.append({"job": job, "score": score})
            print(f"✅ Batch scored {len(jobs)} jobs in 1 Claude call")
        except Exception as e:
            print(f"⚠️ Batch scoring failed, falling back to individual: {e}")
            for job in jobs:
                score = score_job(job)
                scored_jobs.append({"job": job, "score": score})

    scored_jobs = sorted(scored_jobs, key=lambda x: x["score"]["score"], reverse=True)
    top_scored_jobs = scored_jobs[:20]

    apply_count = 0
    review_count = 0
    skip_count = 0
    results: list[dict[str, object]] = []
    apply_jobs: list[dict] = []
    review_jobs: list[dict] = []

    for index, item in enumerate(top_scored_jobs, start=1):
        job = item["job"]
        score = item["score"]
        console.rule(f"Job {index}: {job['title']} at {job['company']}")
        if score["score"] >= APPLY_THRESHOLD:
            if qualifies_for_apply(job):
                decision = "APPLY"
                apply_count += 1
            else:
                decision = "REVIEW"
                review_count += 1
        elif score["score"] >= REVIEW_THRESHOLD:
            decision = "REVIEW"
            review_count += 1
        else:
            decision = "SKIP"
            skip_count += 1

        job["decision"] = decision

        results.append(
            {
                "company": job.get("company", ""),
                "role": job.get("title", ""),
                "location": job.get("location", ""),
                "score": score.get("score", 0),
                "decision": decision,
                "url": job.get("url", ""),
                "why_fit": score.get("why_fit", ""),
                "gaps": score.get("gaps", ""),
            }
        )

        decision_styles = {
            "APPLY": "bold green",
            "REVIEW": "bold yellow",
            "SKIP": "bold red",
        }
        decision_display = f"[{decision_styles[decision]}]{decision}[/{decision_styles[decision]}]"

        table = Table(show_header=False, box=None)
        table.add_row("Company", job["company"])
        table.add_row("Role", job["title"])
        table.add_row("Location", job["location"])
        table.add_row("Salary", job["salary"])
        table.add_row("Source", job.get("source", "-"))
        table.add_row("URL", job.get("url", "-"))
        table.add_row("Score", f"[bold green]{score['score']}[/bold green]/100")
        table.add_row("Decision", decision_display)
        table.add_row("Why Fit", score["why_fit"])
        table.add_row("Best Angle", score["best_angle"])
        table.add_row("Gaps", score["gaps"])
        console.print(table)

        if decision not in ["APPLY", "REVIEW"]:
            if not dry_run:
                record_job(job, decision, score.get("score", 0), email_sent=False, user_id=user_id)
            continue

        # Only generate cover letter for APPLY
        cover_letter = ""
        cover_letter_valid = True
        if decision == "APPLY":
            if mock and dry_run:
                cover_letter = "[mock cover letter — dry-run, no Claude call]"
                print(f"[DRY RUN] Skipping cover letter generation for {job.get('company', '')} | {job.get('title', '')}")
            else:
                cl_result = generate_cover_letter(job)
                if cl_result["valid"]:
                    cover_letter = cl_result["text"]
                    cover_letter_path = os.path.join(
                        cover_letters_dir,
                        _cover_letter_filename(job.get("company", ""), job.get("title", "")),
                    )
                    with open(cover_letter_path, "w", encoding="utf-8") as handle:
                        handle.write(cover_letter)
                    console.print(Panel.fit(cover_letter, title="Tailored Cover Letter", border_style="magenta"))
                else:
                    cover_letter_valid = False
                    console.print(f"[yellow]⚠️ Cover letter failed validation — skipping email for {job.get('company', '')} | {job.get('title', '')}[/yellow]")
                    for issue in cl_result["issues"]:
                        console.print(f"[yellow]  - {issue}[/yellow]")

        if decision == "APPLY":
            apply_jobs.append({
                "company": job.get("company", ""),
                "role": job.get("title", ""),
                "location": job.get("location", ""),
                "salary": job.get("salary") or "Not provided",
                "url": job.get("url", ""),
                "score": score.get("score", 0),
                "cover_letter": cover_letter,
                "cover_letter_valid": cover_letter_valid,
                "_job": job,
            })
        elif decision == "REVIEW":
            review_jobs.append({
                "company": job.get("company", ""),
                "role": job.get("title", ""),
                "location": job.get("location", ""),
                "salary": job.get("salary") or "Not provided",
                "url": job.get("url", ""),
                "score": score.get("score", 0),
                "why_fit": score.get("why_fit", ""),
                "gaps": score.get("gaps", ""),
                "_job": job,
            })

    # Send one consolidated daily report
    today_str = date.today().isoformat()
    total_new = len(apply_jobs) + len(review_jobs)

    if total_new == 0:
        report_subject = safe_ascii(f"[Readymade.Hire] Daily Report — {today_str} — No new jobs")
        report_body = safe_ascii(f"No new jobs found today ({today_str}).")
    else:
        report_subject = safe_ascii(
            f"[Readymade.Hire] Daily Report — {today_str} — {total_new} new job(s)"
        )
        lines: list[str] = [f"DAILY REPORT — {today_str}", f"New jobs: {total_new}", ""]

        if apply_jobs:
            apply_sorted = sorted(apply_jobs, key=lambda x: x["score"], reverse=True)
            lines.append(f"--- APPLY ({len(apply_sorted)} job(s)) ---")
            lines.append("")
            for i, aj in enumerate(apply_sorted, 1):
                lines.append(f"{i}. {aj['company']} — {aj['role']}")
                lines.append(f"   Location : {aj['location']}")
                lines.append(f"   Salary   : {aj['salary']}")
                lines.append(f"   Score    : {aj['score']}/100")
                lines.append(f"   Link     : {aj['url']}")
                lines.append("")
                if aj["cover_letter"]:
                    lines.append("   Cover Letter:")
                    for cl_line in aj["cover_letter"].splitlines():
                        lines.append(f"   {cl_line}")
                else:
                    lines.append("   [Cover letter failed validation — see logs]")
                lines.append("")

        if review_jobs:
            review_sorted = sorted(review_jobs, key=lambda x: x["score"], reverse=True)
            lines.append(f"--- REVIEW ({len(review_sorted)} job(s)) ---")
            lines.append("")
            for i, rj in enumerate(review_sorted, 1):
                lines.append(f"{i}. {rj['company']} — {rj['role']}")
                lines.append(f"   Location : {rj['location']}")
                lines.append(f"   Salary   : {rj['salary']}")
                lines.append(f"   Score    : {rj['score']}/100")
                lines.append(f"   Why Fit  : {rj['why_fit']}")
                lines.append(f"   Gaps     : {rj['gaps']}")
                lines.append(f"   Link     : {rj['url']}")
                lines.append("")

        report_body = safe_ascii("\n".join(lines))

    report_sent = False
    if dry_run or mock:
        prefix = "[DRY RUN]" if dry_run else "[MOCK]"
        print(f"\n{prefix} Would send to: {RECIPIENT_EMAIL}")
        print(f"{prefix} Subject: {report_subject}")
        print(f"{prefix} Body:\n{report_body}")
    else:
        try:
            print(f"📧 SENDING DAILY REPORT TO: {RECIPIENT_EMAIL}")
            send_email(to_email=RECIPIENT_EMAIL, subject=report_subject, body=report_body)
            report_sent = True
            print("✅ DAILY REPORT SENT")
        except Exception as error:
            print("❌ DAILY REPORT EMAIL ERROR:", str(error))

    if not dry_run:
        for entry in apply_jobs:
            record_job(entry["_job"], "APPLY", entry["score"], email_sent=report_sent, user_id=user_id)
        for entry in review_jobs:
            record_job(entry["_job"], "REVIEW", entry["score"], email_sent=report_sent, user_id=user_id)

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    top_results = results[:20]

    jobs_output_path = os.path.join(output_dir, "jobs.json")
    with open(jobs_output_path, "w", encoding="utf-8") as handle:
        json.dump(top_results, handle, indent=2)

    console.print("\n[bold green]Done.[/bold green] Evaluated all jobs.")
    summary = Table(show_header=False, box=None)
    summary.add_row("Total jobs evaluated", str(len(scored_jobs)))
    summary.add_row("Top jobs processed", str(len(top_scored_jobs)))
    summary.add_row("APPLY", f"[bold green]{apply_count}[/bold green]")
    summary.add_row("REVIEW", f"[bold yellow]{review_count}[/bold yellow]")
    summary.add_row("SKIP", f"[bold red]{skip_count}[/bold red]")
    console.print("\n[bold]Summary:[/bold]")
    console.print(summary)


def run_pipeline(user_id: str = "default"):
    """Wrapper so Cloud Run server can trigger the pipeline."""
    run(user_id=user_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Readymade.hire job pipeline")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock job data (jobs_test.db); skips real email send",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Skip email send and DB writes; combine with --mock to also skip Claude calls",
    )
    args = parser.parse_args()
    run(mock=args.mock, dry_run=args.dry_run)