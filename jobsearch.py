"""
Job matching & application-support CLI.
Uses jobsearch_lib. Does NOT auto-submit applications.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import jobsearch_lib as lib

SCRIPT_DIR = Path(__file__).resolve().parent


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Missing {name}. Add to environment.env")
        sys.exit(1)
    return value


def main() -> None:
    lib.load_env_files()
    parser = argparse.ArgumentParser(description="Germany-focused job matcher")
    parser.add_argument("--cv", type=Path, default=None)
    parser.add_argument("--min-score", type=int, default=70)
    parser.add_argument("--max-jobs", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--use-cache", action="store_true")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument(
        "--all-locations",
        action="store_true",
        help="Disable Germany filter (default: Germany + remote EU only)",
    )
    args = parser.parse_args()

    mistral_key = require_env("MISTRAL_API_KEY")
    cv_path = args.cv.resolve() if args.cv else lib.resolve_default_cv()
    cv = lib.load_cv(cv_path)
    profile = lib.load_profile()

    if args.refresh_cache:
        token = require_env("APIFY_TOKEN")
        ds = os.getenv("APIFY_DATASET_ID", "").strip()
        jobs = lib.fetch_jobs(token, ds)
        print(f"Cache refreshed: {len(jobs)} jobs")
        return

    if args.use_cache:
        jobs = lib.load_cached_jobs()
    else:
        token = require_env("APIFY_TOKEN")
        ds = os.getenv("APIFY_DATASET_ID", "").strip()
        jobs = lib.fetch_jobs(token, ds)

    if not args.all_locations:
        before = len(jobs)
        jobs = lib.filter_germany_jobs(jobs)
        print(f"Germany filter: {before} -> {len(jobs)} jobs")

    if args.max_jobs > 0:
        jobs = jobs[: args.max_jobs]

    run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = SCRIPT_DIR / "output" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"CV: {cv_path.name} ({len(cv)} chars)")
    print(f"Processing {len(jobs)} jobs -> {out_dir}\n")

    results = []
    generated = 0

    for i, job in enumerate(jobs, 1):
        desc, about, title, company = lib.job_text_fields(job)
        if not desc:
            print(f"[{i}/{len(jobs)}] skip (no description): {title}")
            continue

        print(f"[{i}/{len(jobs)}] {title} @ {company} ...", end=" ", flush=True)
        try:
            match = lib.match_job(mistral_key, cv, job, profile)
        except Exception as exc:
            print(f"ERROR {exc}")
            continue

        score = int(match.get("match_score", 0))
        rec = match.get("recommendation", "skip")
        loc = job.get("location") or ""
        print(f"{score} -> {rec}")

        materials = None
        if not args.dry_run and lib.should_generate(match, args.min_score):
            print("    generating materials ...", end=" ", flush=True)
            try:
                materials = lib.generate_materials(mistral_key, cv, job, match, profile)
                generated += 1
                print("ok")
            except Exception as exc:
                print(f"ERROR {exc}")

        lib.write_job_output(out_dir, job, title, company, match, materials)
        results.append(
            {
                "score": score,
                "recommendation": rec,
                "company": company,
                "title": title,
                "location": loc,
            }
        )
        time.sleep(2)

    (out_dir / "summary.md").write_text(lib.build_summary_md(results, out_dir), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"\nDone. Scored: {len(results)} | Generated: {generated}")
    print(f"Summary: {out_dir / 'summary.md'}")
    print("UI: streamlit run streamlit_app.py")


if __name__ == "__main__":
    main()
