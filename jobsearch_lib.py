"""Shared library for job matching pipeline and Streamlit UI."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from html import unescape
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
JOBS_CACHE_PATH = SCRIPT_DIR / "data" / "jobs_cache.json"
PROFILE_PATH = SCRIPT_DIR / "profile.json"
CV_PROFILE_PATH = SCRIPT_DIR / "data" / "cv_profile.json"
QUALIFICATIONS_PATH = SCRIPT_DIR / "data" / "qualifications.json"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")

GERMANY_KEYWORDS = re.compile(
    r"\b(germany|deutschland|frankfurt|hanau|hesse|hessen|offenbach|"
    r"main-kinzig|mainz|wiesbaden|darmstadt)\b",
    re.IGNORECASE,
)

MATCH_SCHEMA = """
Return ONLY valid JSON with:
{
  "match_score": <0-100 based on REQUIREMENTS not job title>,
  "recommendation": "apply" | "review" | "skip",
  "role_category": "<best-fit family>",
  "title_vs_requirements_note": "<does title match posting requirements?>",
  "requirements_analysis": [
    {"requirement": "", "section": "must-have|preferred|responsibility|education|logistics",
     "status": "met|partial|missing", "evidence": ""}
  ],
  "must_have_met_count": 0,
  "must_have_total": 0,
  "required_met": [],
  "required_missing": [],
  "preferred_met": [],
  "transferable_bridges": [],
  "dealbreakers": [],
  "logistics_ok": true,
  "logistics_notes": "",
  "cultural_fit_summary": "",
  "reasoning": ""
}
"""

MATERIALS_SCHEMA = """
Return ONLY valid JSON with:
{
  "tailored_resume": "...",
  "cover_letter": "...",
  "key_angles": []
}
"""


def load_env_files() -> None:
    for name in ("environment.env", ".env"):
        path = SCRIPT_DIR / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        return {}
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    clusters = profile.get("search_keyword_clusters", {})
    if clusters and not profile.get("all_search_keywords"):
        flat: list[str] = []
        for terms in clusters.values():
            flat.extend(terms)
        profile["all_search_keywords"] = sorted(set(flat))
    return profile


def load_qualifications() -> dict:
    """Structured qualification inventory for requirements-based matching."""
    if QUALIFICATIONS_PATH.exists():
        return json.loads(QUALIFICATIONS_PATH.read_text(encoding="utf-8"))
    if CV_PROFILE_PATH.exists():
        return json.loads(CV_PROFILE_PATH.read_text(encoding="utf-8"))
    return {}


def build_matching_context(cv: str, profile: dict | None = None) -> str:
    profile = profile or load_profile()
    quals = load_qualifications()
    return f"""## Full CV text
{cv}

## Candidate profile (locations, eligibility, strategy)
{json.dumps(profile, indent=2)}

## Structured qualifications inventory (source of truth for matching)
{json.dumps(quals, indent=2)}

## Matching rules
1. IGNORE job title unless it clearly contradicts the description.
2. Extract requirements from: Qualifications, Requirements, Must have, Nice to have, Responsibilities, What you bring, Your profile, Skills, Education, Languages, Location.
3. Titles vary widely (e.g. "Associate", "Specialist", "Analyst", "Engineer", "Consultant", "Werkstudent") — match on requirements only.
4. Map each must-have to qualifications using transferable skills (Nordic ECTS = degree or equivalent experience).
5. Recognize role families and title aliases in qualifications.role_families_eligible and title_aliases_to_recognize.
6. STEM/environment courses qualify for junior ESG/energy/data crossover roles when requirements align.
7. Dell support + multilingual + documentation qualify for customer success, application support, service desk.
8. Do not invent skills. Use partial when adjacent coursework or experience applies.
9. EU citizen — Germany/EU work authorized unless posting requires specific license candidate lacks.
"""


def html_to_text(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|li|h[1-6]|div|section|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def resolve_default_cv() -> Path:
    for name in ("cv.html", "cv.pdf", "cv.txt"):
        path = SCRIPT_DIR / name
        if path.exists():
            return path
    return SCRIPT_DIR / "cv.html"


def load_cv(cv_path: Path | None = None) -> str:
    path = cv_path or resolve_default_cv()
    if not path.exists():
        raise FileNotFoundError(f"CV not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(p.extract_text() or "" for p in reader.pages).strip()
    elif suffix in (".html", ".htm"):
        text = html_to_text(path.read_text(encoding="utf-8"))
    else:
        text = path.read_text(encoding="utf-8").strip()
    if len(text) < 100:
        raise ValueError("CV too short")
    return text


def slugify(*parts: str, max_len: int = 80) -> str:
    raw = "_".join(p for p in parts if p)
    raw = re.sub(r"[^\w\s-]", "", raw.lower())
    raw = re.sub(r"[\s_-]+", "_", raw).strip("_")
    return raw[:max_len] or "job"


def parse_json_response(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def mistral_json(api_key: str, system: str, user: str, retries: int = 3) -> dict:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    last_error = None
    for attempt in range(retries + 1):
        response = requests.post(MISTRAL_URL, json=payload, headers=headers, timeout=120)
        result = response.json()
        if "choices" not in result:
            is_rate_limit = response.status_code == 429 or result.get("code") == "1300"
            if is_rate_limit and attempt < retries:
                wait = min(60, 5 * (2**attempt))
                time.sleep(wait)
                continue
            raise RuntimeError(f"Mistral error: {result}")
        try:
            return parse_json_response(result["choices"][0]["message"]["content"])
        except json.JSONDecodeError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Invalid JSON from Mistral: {last_error}")


def load_cached_jobs() -> list[dict]:
    if not JOBS_CACHE_PATH.exists():
        raise FileNotFoundError(f"No cache at {JOBS_CACHE_PATH}")
    data = json.loads(JOBS_CACHE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Cache empty")
    return data


def save_jobs_cache(jobs: list[dict]) -> None:
    JOBS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOBS_CACHE_PATH.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def fetch_jobs(apify_token: str, dataset_id: str) -> list[dict]:
    url = (
        f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        f"?clean=true&token={apify_token}"
    )
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError("Dataset empty")
    save_jobs_cache(data)
    return data


def is_germany_job(job: dict) -> bool:
    """Heuristic: job location/country mentions Germany or target cities."""
    parts = [
        str(job.get("location") or ""),
        str(job.get("country") or ""),
        str(job.get("descriptionText") or "")[:500],
    ]
    blob = " ".join(parts)
    if GERMANY_KEYWORDS.search(blob):
        return True
    if str(job.get("country", "")).upper() in ("DE", "DEU", "GERMANY"):
        return True
    return False


def filter_germany_jobs(jobs: list[dict], remote_eu_ok: bool = True) -> list[dict]:
    filtered = []
    for job in jobs:
        if is_germany_job(job):
            filtered.append(job)
            continue
        if remote_eu_ok and job.get("workRemoteAllowed"):
            wt = job.get("workplaceTypes") or []
            if "Remote" in wt or job.get("workRemoteAllowed") is True:
                filtered.append(job)
    return filtered


def job_text_fields(job: dict) -> tuple[str, str, str, str]:
    description = (
        job.get("descriptionText")
        or job.get("descriptionHtml")
        or job.get("jobDescription")
        or ""
    ).strip()
    about_us = (job.get("companyDescription") or "").strip()
    title = (job.get("title") or "Unknown title").strip()
    company = (job.get("companyName") or "Unknown company").strip()
    return description, about_us, title, company


def match_job(
    api_key: str,
    cv: str,
    job: dict,
    profile: dict | None = None,
) -> dict:
    description, about_us, title, company = job_text_fields(job)
    profile = profile or load_profile()
    loc_prefs = profile.get("location_preferences", {})
    about_block = f"\n## Company About Us\n{about_us}\n" if about_us else ""
    context = build_matching_context(cv, profile)

    system = (
        "You are a requirements-based job-fit analyst. The job TITLE is only a hint — "
        "always parse the full posting and score against the candidate's qualification inventory. "
        "The same candidate may fit jobs with unrelated titles (e.g. 'Analyst' for support, "
        "'Specialist' for QA, 'Coordinator' for integration). "
        "Candidate targets Germany (Frankfurt, Hanau, Hesse) and remote Germany/EU. "
        f"{MATCH_SCHEMA}"
    )
    user = f"""{context}

## Job posting to analyze
Listed title (do NOT score on title alone): {title}
Company: {company}
Location: {job.get('location')}
Country: {job.get('country')}
Remote: {job.get('workRemoteAllowed')}
Workplace: {job.get('workplaceTypes')}
Seniority: {job.get('seniorityLevel')}
Employment: {job.get('employmentType')}

## Full job description (extract ALL requirements from this text)
{description}
{about_block}

Location preference: {loc_prefs.get('cities', [])}, Germany.
Scoring: match_score = weighted must-have coverage (70%) + preferred (20%) + logistics (10%).
- 85-100 and no dealbreakers → apply
- 65-84 or minor gaps → review
- below 65 or any hard dealbreaker → skip
Populate requirements_analysis with at least 5 items when posting has enough detail.
"""
    return mistral_json(api_key, system, user)


def generate_materials(
    api_key: str,
    cv: str,
    job: dict,
    match: dict,
    profile: dict | None = None,
) -> dict:
    description, about_us, title, company = job_text_fields(job)
    profile = profile or load_profile()
    about_block = f"\n## Company About Us\n{about_us}\n" if about_us else ""
    system = (
        "Write truthful tailored application materials. Only facts from CV. "
        "Emphasize flexible education and transferable skills for Germany market. "
        f"{MATERIALS_SCHEMA}"
    )
    user = f"""CV:\n{cv}\n\nProfile:\n{json.dumps(profile)}\n\nRole: {title} @ {company}\n\nMatch:\n{json.dumps(match)}\n\nJob:\n{description}\n{about_block}"""
    return mistral_json(api_key, system, user)


def should_generate(match: dict, min_score: int) -> bool:
    if match.get("dealbreakers"):
        return False
    if match.get("recommendation") == "skip":
        return False
    return int(match.get("match_score", 0)) >= min_score


def write_job_output(
    out_dir: Path,
    job: dict,
    title: str,
    company: str,
    match: dict,
    materials: dict | None,
) -> Path:
    folder = out_dir / slugify(company, title)
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "title": title,
        "company": company,
        "location": job.get("location"),
        "country": job.get("country"),
        "remote": job.get("workRemoteAllowed"),
        "workplace_types": job.get("workplaceTypes"),
        "seniority": job.get("seniorityLevel"),
        "apply_url": job.get("applyUrl") or job.get("link") or "",
        "match": match,
        "description_preview": (job.get("descriptionText") or "")[:2000],
    }
    (folder / "match.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if job.get("descriptionText"):
        (folder / "job_description.txt").write_text(
            job.get("descriptionText", ""), encoding="utf-8"
        )
    if materials:
        (folder / "tailored_resume.txt").write_text(
            materials.get("tailored_resume", ""), encoding="utf-8"
        )
        (folder / "cover_letter.txt").write_text(
            materials.get("cover_letter", ""), encoding="utf-8"
        )
        angles = materials.get("key_angles") or []
        if angles:
            (folder / "positioning_notes.txt").write_text(
                "\n".join(f"- {a}" for a in angles), encoding="utf-8"
            )
    return folder


def build_summary_md(results: list[dict], out_dir: Path) -> str:
    lines = [
        "# Job match run",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Output: `{out_dir}`",
        "",
        "| Score | Action | Location | Company | Title |",
        "|------:|--------|----------|---------|-------|",
    ]
    for r in sorted(results, key=lambda x: -x["score"]):
        lines.append(
            f"| {r['score']} | {r['recommendation']} | {r.get('location', '')} | "
            f"{r['company']} | {r['title']} |"
        )
    lines.extend([
        "",
        "## Next steps",
        "1. Review **apply** and **review** in Streamlit: `streamlit run streamlit_app.py`",
        "2. Edit tailored files before submitting.",
        "3. Apply manually via apply_url in match.json.",
    ])
    return "\n".join(lines)


def list_output_runs() -> list[Path]:
    out = SCRIPT_DIR / "output"
    if not out.exists():
        return []
    runs = [p for p in out.iterdir() if p.is_dir()]
    return sorted(runs, key=lambda p: p.name, reverse=True)


def load_run_jobs(run_dir: Path) -> list[dict]:
    jobs = []
    for folder in run_dir.iterdir():
        match_file = folder / "match.json"
        if not match_file.exists():
            continue
        data = json.loads(match_file.read_text(encoding="utf-8"))
        data["folder"] = str(folder)
        data["folder_name"] = folder.name
        jobs.append(data)
    return sorted(jobs, key=lambda j: -int(j.get("match", {}).get("match_score", 0)))
