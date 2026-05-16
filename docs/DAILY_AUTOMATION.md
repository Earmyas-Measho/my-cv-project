# Daily Automation Plan

## Overview

```
Apify (scheduled scrape, DE) → Dataset → jobsearch.py (score + materials) → Streamlit (review) → You apply manually
```

---

## 1. Schedule Apify (Germany jobs)

1. Open your Apify actor (LinkedIn Jobs Scraper).
2. Paste input from `config/apify_linkedin_germany.json`.
3. Set schedule: **once daily** (e.g. 06:00 CET) — respects ~100 jobs/day limit.
4. Point dataset ID to `APIFY_DATASET_ID` in `environment.env`.
5. Optional: webhook to your future cloud API (Phase 2).

**Do not refresh cache repeatedly during development** — use `--use-cache`.

---

## 2. Daily scoring run

```powershell
cd C:\Users\ivana\OneDrive\Desktop\job

# Morning: pull new jobs (once)
python jobsearch.py --refresh-cache

# Score + generate materials (Germany filter on by default)
python jobsearch.py --use-cache --min-score 75
```

**Cost control:** use `--dry-run` first to see scores only; generate letters for `--min-score 80+`.

---

## 3. Review matches (15–30 min/day)

```powershell
streamlit run streamlit_app.py
```

1. Select latest output run.
2. Filter: **apply** + **review**, score ≥ 75.
3. Read Match tab → Description → tailored Resume/Cover letter.
4. Edit anything inaccurate (never submit unreviewed AI text).
5. Click **Open apply link** → apply on LinkedIn/company site.

---

## 4. Apply manually

- **Do not** auto-apply (LinkedIn ToS, wrong-application risk).
- Target: **5–10 quality applications/day**, not 100 spam applies.
- Track in spreadsheet: company, date, status, follow-up.

---

## 5. Scale toward 100 qualified jobs/day

| Stage | Volume | How |
|-------|--------|-----|
| **Now** | 100 scraped → ~10–30 Germany-relevant → ~5–15 qualified | Germany filter + min-score 75 |
| **Month 1** | Expand keywords in Apify config | Add role variants from `docs/JOB_ROLES.md` |
| **Month 2** | Host on Railway/Render | Scheduled API + email digest of top 10 |
| **Month 3** | Multiple Apify runs (regions/keywords) | 2–3 scheduled actors if budget allows |
| **Realistic apply cap** | 5–15 applies/day | Human review bottleneck — quality over quantity |

“100 qualified jobs/day” means **100 jobs scored and ranked** — not 100 applications submitted.

---

## Weekly checklist

- [ ] Monday: `--refresh-cache` + full `--use-cache` run  
- [ ] Daily: Streamlit review + 5 applies  
- [ ] Friday: tune `profile.json` keywords / min-score  
- [ ] Monthly: update `cv.html`, rerun best matches  

---

## Environment file

Use `environment.env`:

```
APIFY_TOKEN=...
MISTRAL_API_KEY=...
APIFY_DATASET_ID=...
```

Never commit real keys to git.
