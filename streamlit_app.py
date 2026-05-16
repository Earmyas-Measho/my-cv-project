"""
Streamlit dashboard for job matching results.
Run: streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import jobsearch_lib as lib

lib.load_env_files()

st.set_page_config(
    page_title="Job Matcher — Germany",
    page_icon="💼",
    layout="wide",
)

st.title("Job Matching Dashboard")
st.caption("Germany focus · Frankfurt · Hanau · Review before applying")

profile = lib.load_profile()
if profile:
    with st.expander("Your profile", expanded=False):
        st.json(profile)

runs = lib.list_output_runs()
if not runs:
    st.warning("No output runs yet. Run: `python jobsearch.py --use-cache --max-jobs 5`")
    st.stop()

run_names = [r.name for r in runs]
selected_run = st.sidebar.selectbox("Output run", run_names, index=0)
run_dir = lib.SCRIPT_DIR / "output" / selected_run

jobs = lib.load_run_jobs(run_dir)
if not jobs:
    st.warning("No job results in this run.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")
min_score = st.sidebar.slider("Minimum score", 0, 100, 0)
rec_filter = st.sidebar.multiselect(
    "Recommendation",
    ["apply", "review", "skip"],
    default=["apply", "review"],
)
loc_query = st.sidebar.text_input("Location contains", "")
title_query = st.sidebar.text_input("Title contains", "")
role_query = st.sidebar.text_input("Role category contains", "")
remote_only = st.sidebar.checkbox("Remote allowed only", False)
st.sidebar.caption("Matching uses job **requirements**, not title. Re-run pipeline for new analysis.")

filtered = []
for j in jobs:
    m = j.get("match", {})
    score = int(m.get("match_score", 0))
    rec = m.get("recommendation", "skip")
    if score < min_score:
        continue
    if rec_filter and rec not in rec_filter:
        continue
    loc = (j.get("location") or "").lower()
    if loc_query and loc_query.lower() not in loc:
        continue
    title = (j.get("title") or "").lower()
    if title_query and title_query.lower() not in title:
        continue
    cat = (j.get("match", {}).get("role_category") or "").lower()
    if role_query and role_query.lower() not in cat:
        continue
    if remote_only and not j.get("remote"):
        continue
    filtered.append(j)

st.sidebar.metric("Jobs shown", len(filtered), f"of {len(jobs)}")

# Summary metrics
cols = st.columns(4)
apply_n = sum(1 for j in filtered if j.get("match", {}).get("recommendation") == "apply")
review_n = sum(1 for j in filtered if j.get("match", {}).get("recommendation") == "review")
cols[0].metric("Apply", apply_n)
cols[1].metric("Review", review_n)
cols[2].metric("Avg score", round(
    sum(int(j.get("match", {}).get("match_score", 0)) for j in filtered) / max(len(filtered), 1)
))
cols[3].metric("Run", selected_run)

# Job table
st.subheader("Jobs")
for j in filtered:
    m = j.get("match", {})
    score = int(m.get("match_score", 0))
    rec = m.get("recommendation", "?")
    label = f"[{score}] {rec.upper()} — {j.get('title')} @ {j.get('company')}"
    with st.expander(label, expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Location:** {j.get('location', '—')}")
        c2.write(f"**Category:** {m.get('role_category', '—')}")
        c3.write(f"**Remote:** {j.get('remote', '—')}")

        apply_url = j.get("apply_url") or ""
        if apply_url:
            st.link_button("Open apply link", apply_url, use_container_width=False)

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Match", "Description", "Resume", "Cover letter", "Notes"]
        )

        with tab1:
            st.markdown(f"**Role category (fit):** {m.get('role_category', '—')}")
            note = m.get("title_vs_requirements_note")
            if note:
                st.info(note)
            mh = m.get("must_have_met_count")
            mt = m.get("must_have_total")
            if mh is not None and mt:
                st.progress(min(1.0, int(mh) / max(int(mt), 1)))
                st.caption(f"Must-haves met: {mh} / {mt}")
            st.markdown(f"**Reasoning:** {m.get('reasoning', '')}")
            req_rows = m.get("requirements_analysis") or []
            if req_rows:
                st.markdown("**Requirements vs your qualifications**")
                st.dataframe(req_rows, use_container_width=True, hide_index=True)
            st.markdown("**Required met**")
            st.write(m.get("required_met", []))
            st.markdown("**Missing**")
            st.write(m.get("required_missing", []))
            bridges = m.get("transferable_bridges") or []
            if bridges:
                st.markdown("**Transferable bridges**")
                st.write(bridges)
            st.markdown("**Dealbreakers**")
            st.write(m.get("dealbreakers", []))
            st.markdown(f"**Culture:** {m.get('cultural_fit_summary', '')}")

        folder = Path(j.get("folder", ""))
        with tab2:
            desc_path = folder / "job_description.txt"
            if desc_path.exists():
                st.text_area("Description", desc_path.read_text(encoding="utf-8"), height=300)
            else:
                st.text(j.get("description_preview", "No description saved"))

        with tab3:
            resume_path = folder / "tailored_resume.txt"
            if resume_path.exists():
                st.text_area("Tailored resume", resume_path.read_text(encoding="utf-8"), height=400)
            else:
                st.info("No tailored resume (score below threshold or dry-run)")

        with tab4:
            cl_path = folder / "cover_letter.txt"
            if cl_path.exists():
                st.text_area("Cover letter", cl_path.read_text(encoding="utf-8"), height=400)
            else:
                st.info("No cover letter generated")

        with tab5:
            notes_path = folder / "positioning_notes.txt"
            if notes_path.exists():
                st.text(notes_path.read_text(encoding="utf-8"))
            else:
                st.json(m)

st.sidebar.divider()
st.sidebar.markdown("### Commands")
st.sidebar.code("python jobsearch.py --use-cache --dry-run")
st.sidebar.code("python jobsearch.py --use-cache --min-score 75")
st.sidebar.code("python jobsearch.py --refresh-cache")
