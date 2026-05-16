# Job Matching System — Complete Guide

**Candidate:** Earmyas Measho Gebre · **Market:** Germany (Frankfurt, Hanau) · **CV:** `cv.html`

---

## Quick start

```powershell
cd C:\Users\ivana\OneDrive\Desktop\job
pip install -r requirements.txt
# Edit environment.env with your API keys
python jobsearch.py --use-cache --max-jobs 5 --dry-run
streamlit run streamlit_app.py
```

---

## Section index

| # | Section | File |
|---|---------|------|
| 1 | CV Analysis | [CV_ANALYSIS.md](CV_ANALYSIS.md) · `data/cv_profile.json` |
| 2 | Job Roles You Qualify For | [JOB_ROLES.md](JOB_ROLES.md) |
| 3 | Germany Job Filters | `profile.json` |
| 4 | Apify Scraper Config | `../config/apify_linkedin_germany.json` |
| 5 | Python Pipeline | `../jobsearch.py` · `../jobsearch_lib.py` |
| 6 | Streamlit UI | `../streamlit_app.py` |
| 7 | .env Template | `../environment.env.example` |
| 8 | Daily Automation | [DAILY_AUTOMATION.md](DAILY_AUTOMATION.md) |

---

## Requirements-based matching

The system **ignores job titles** and parses posting text (Qualifications, Must have, Responsibilities, etc.), mapping each line to `data/qualifications.json`.

Output per job includes `requirements_analysis[]` with `met|partial|missing` + evidence.

Search uses **90+ role keywords** in `profile.json` (10 clusters) + 5 rotating Apify batches in `config/apify_keyword_batches.json`.

---

## Pipeline flags

| Flag | Purpose |
|------|---------|
| `--use-cache` | Read `data/jobs_cache.json` (no Apify call) |
| `--refresh-cache` | Fetch Apify dataset → save cache → exit |
| `--max-jobs N` | Process only first N jobs |
| `--min-score N` | Generate resume/letter only if score ≥ N |
| `--dry-run` | Score only, no materials |
| `--all-locations` | Disable Germany filter |

---

## File structure

```
job/
  cv.html
  profile.json
  environment.env
  jobsearch.py
  jobsearch_lib.py
  streamlit_app.py
  config/apify_linkedin_germany.json
  data/jobs_cache.json
  data/cv_profile.json
  output/<run>/
    summary.md
    <company>_<role>/
      match.json
      job_description.txt
      tailored_resume.txt
      cover_letter.txt
  docs/
```
