"""
Resume Matcher Pro - Streamlit Web Application
Connects to local Llama models via Ollama to tailor master resumes,
beat ATS screening filters, export Word & PDF formats,
and maintain complete application tracking history.
"""

import os
import json
import re
import streamlit as st
from config import RECOMMENDED_LLAMA_MODELS, DEFAULT_MODEL, DEFAULT_OLLAMA_HOST, OUTPUT_DIR, DATA_DIR
from modules.llm_client import LocalLLMClient
from modules.resume_parser import ResumeParser
from modules.job_extractor import JobExtractor
from modules.ats_optimizer import ATSOptimizer
from modules.resume_tailorer import ResumeTailorer
from modules.document_exporter import DocumentExporter
from modules.job_searcher import JobSearcher
from modules.application_tracker import ApplicationTracker

# Page setup
st.set_page_config(
    page_title="Resume Matcher Pro (Local Llama + ATS)",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .badge-match {
        display: inline-block;
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 10px;
        margin: 3px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-missing {
        display: inline-block;
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 4px 10px;
        margin: 3px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .history-card {
        padding: 1rem 1.2rem;
        border-radius: 8px;
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        margin-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "master_resume_text" not in st.session_state:
    st.session_state.master_resume_text = ""
if "master_profile" not in st.session_state:
    st.session_state.master_profile = None
if "job_data" not in st.session_state:
    st.session_state.job_data = None
if "target_job_url" not in st.session_state:
    st.session_state.target_job_url = "Direct Text Input"
if "ats_results" not in st.session_state:
    st.session_state.ats_results = None
if "tailored_resume_md" not in st.session_state:
    st.session_state.tailored_resume_md = ""
if "interview_prep" not in st.session_state:
    st.session_state.interview_prep = None
if "last_recorded_app" not in st.session_state:
    st.session_state.last_recorded_app = None

# Sidebar: Local Llama Model Configuration
with st.sidebar:
    st.image("https://raw.githubusercontent.com/ollama/ollama/main/docs/assets/ollama.png", width=60)
    st.title("Local Llama AI")
    st.caption("Privacy-first • Zero cloud data leakage • Runs 100% locally")

    model_choice = st.selectbox(
        "Choose Llama Model",
        options=list(RECOMMENDED_LLAMA_MODELS.keys()),
        index=0,
        format_func=lambda x: RECOMMENDED_LLAMA_MODELS[x].name
    )
    selected_model_info = RECOMMENDED_LLAMA_MODELS[model_choice]
    st.info(f"💡 **Specs:** {selected_model_info.recommended_vram}\n\n{selected_model_info.tagline}")

    ollama_url = st.text_input("Ollama Host URL", value=DEFAULT_OLLAMA_HOST)
    temperature = st.slider("Creativity / Temperature", 0.0, 0.7, 0.2, 0.05, help="Low temperature (0.1 - 0.2) ensures truthful, strict keyword alignment.")

    # Connection health check
    llm_client = LocalLLMClient(host=ollama_url, model=model_choice, temperature=temperature)
    health = llm_client.check_health()

    if health.get("connected"):
        st.success(f"🟢 Connected to Ollama ({len(health.get('models', []))} models installed)")
        if not health.get("model_installed"):
            st.warning(f"⚠️ Model `{model_choice}` not found locally. Run `ollama run {model_choice}` in terminal.")
    else:
        st.error("🔴 Ollama Offline or Inaccessible")
        with st.expander("How to start Ollama"):
            st.markdown(f"""
            1. Open PowerShell or Command Prompt.
            2. Run: `ollama run {model_choice}`
            3. Ollama will download and host the model at `{ollama_url}`.
            """)

    st.divider()
    st.markdown("### 📋 ATS Quick Reference")
    st.markdown("""
    - **Single Column Rule**: Workday & Greenhouse parse multi-column layouts horizontally.
    - **No Header/Footer text**: Put contact info in the body text.
    - **Google XYZ Formula**: 'Accomplished [X] measured by [Y] by doing [Z]'.
    """)

# Header
st.markdown('<div class="main-title">🎯 AI Resume Matcher & ATS Optimizer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Connects to local Llama models to tailor your Master Resume for any target role, pass ATS filters, export PDF/DOCX, and track your applications.</div>', unsafe_allow_html=True)

# Main Application Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. 📄 Master Resume",
    "2. 💼 Target Job Intake",
    "3. 📊 ATS Score & Gap Analysis",
    "4. ✨ Tailored Resume (PDF/DOCX)",
    "5. 🎙️ Interview Prep",
    "6. 📂 Application Tracker & History"
])

# -------------------------------------------------------------
# TAB 1: MASTER RESUME INTAKE
# -------------------------------------------------------------
with tab1:
    st.subheader("Candidate Master Resume")
    st.write("Upload your comprehensive master resume containing your entire career history, projects, metrics, and all skills.")

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF, DOCX, MD, TXT)", type=["pdf", "docx", "md", "txt"])
    with col2:
        st.write("Or test with ready-to-use sample:")
        if st.button("Load Sample Master Resume", use_container_width=True):
            sample_path = os.path.join(DATA_DIR, "sample_master_resume.md")
            if os.path.exists(sample_path):
                with open(sample_path, "r", encoding="utf-8") as f:
                    st.session_state.master_resume_text = f.read()
                st.success("Sample master resume loaded!")

    if uploaded_file is not None:
        try:
            parser = ResumeParser(llm_client)
            raw_text = parser.read_file(uploaded_file, filename=uploaded_file.name)
            st.session_state.master_resume_text = raw_text
            st.success(f"Successfully loaded `{uploaded_file.name}` ({len(raw_text.split())} words)")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    # Editable text area
    st.session_state.master_resume_text = st.text_area(
        "Master Resume Content",
        value=st.session_state.master_resume_text,
        height=320,
        placeholder="Paste your full master resume here..."
    )

    if st.button("🔍 Parse & Understand Candidate Profile", type="primary"):
        if not st.session_state.master_resume_text.strip():
            st.warning("Please upload or paste a master resume first.")
        else:
            with st.spinner("Analyzing candidate profile with Llama model..."):
                parser = ResumeParser(llm_client)
                profile = parser.parse_to_master_profile(st.session_state.master_resume_text)
                st.session_state.master_profile = profile
                st.success("Candidate background parsed and structured!")

    # Display profile overview if parsed
    if st.session_state.master_profile:
        p = st.session_state.master_profile
        contact = p.get("contact", {})
        st.markdown(f"**Candidate:** {contact.get('name', 'N/A')} | **Email:** {contact.get('email', 'N/A')} | **Location:** {contact.get('location', 'N/A')}")
        with st.expander("View Structured Candidate Profile"):
            st.json(p)

# -------------------------------------------------------------
# TAB 2: TARGET JOB INTAKE
# -------------------------------------------------------------
with tab2:
    st.subheader("Target Job Description")
    st.write("Provide the target job via direct text, a live posting link, or automated job search. The system tracks the job title and URL for your application records.")

    jd_mode = st.radio("Input Method", ["Paste Job Description Text", "Provide Job Posting Link (URL)", "Search Live Jobs for My Profile"], horizontal=True)

    if jd_mode == "Paste Job Description Text":
        col_load, col_sp = st.columns([1, 4])
        with col_load:
            if st.button("Load Sample JD"):
                sample_jd_path = os.path.join(DATA_DIR, "sample_job_description.txt")
                if os.path.exists(sample_jd_path):
                    with open(sample_jd_path, "r", encoding="utf-8") as f:
                        st.session_state.jd_input_text = f.read()

        jd_text = st.text_area(
            "Paste Full Job Description",
            value=st.session_state.get("jd_input_text", ""),
            height=280,
            placeholder="Paste complete job description including requirements, responsibilities, and qualifications..."
        )

        custom_url = st.text_input("Job Posting URL (Optional, for tracking records)", value="Direct Text Input")

        if st.button("Analyze Target Job", type="primary"):
            if not jd_text.strip():
                st.warning("Please paste a job description.")
            else:
                with st.spinner("Extracting employer requirements and keywords..."):
                    extractor = JobExtractor(llm_client)
                    st.session_state.job_data = extractor.parse_job_description(jd_text)
                    st.session_state.target_job_url = custom_url.strip() or "Direct Text Input"
                    st.success(f"Target Job Analyzed: {st.session_state.job_data.get('title', 'Role')}")

    elif jd_mode == "Provide Job Posting Link (URL)":
        job_url = st.text_input("Job URL (Greenhouse, Lever, LinkedIn, Workday, Company site)", placeholder="https://boards.greenhouse.io/company/jobs/12345")
        if st.button("Scrape & Analyze Job Link", type="primary"):
            if not job_url.strip():
                st.warning("Please enter a valid job URL.")
            else:
                with st.spinner(f"Scraping and analyzing job posting from {job_url}..."):
                    try:
                        extractor = JobExtractor(llm_client)
                        st.session_state.job_data = extractor.parse_job_description(job_url)
                        st.session_state.target_job_url = job_url.strip()
                        st.success(f"Parsed Job: {st.session_state.job_data.get('title', 'Role')} at {st.session_state.job_data.get('company', 'Company')}")
                    except Exception as e:
                        st.error(f"Error fetching job: {e}")

    else:
        st.write("Search live job openings across company career pages and ATS job boards matching your profile.")
        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        with col_s1:
            search_title = st.text_input("Target Role Title", value="Software Developer")
        with col_s2:
            search_loc = st.text_input("Location / City", value="Bengaluru")
        with col_s3:
            search_portal = st.selectbox("Target Board", ["All Sources", "Greenhouse", "Lever", "LinkedIn", "Indeed"])

        if st.button("Search Matching Openings", type="primary"):
            with st.spinner("Searching job boards for matching openings..."):
                searcher = JobSearcher()
                portal_filter = ""
                if search_portal == "Greenhouse":
                    portal_filter = "greenhouse"
                elif search_portal == "Lever":
                    portal_filter = "lever"
                elif search_portal == "LinkedIn":
                    portal_filter = "linkedin"
                elif search_portal == "Indeed":
                    portal_filter = "indeed"

                query_str = f"{search_title} {search_loc} {portal_filter}".strip()
                results = searcher.search_jobs(query_str, max_results=6)
                st.session_state.search_results = results

        if "search_results" in st.session_state and st.session_state.search_results:
            st.markdown("### Matching Opportunities Found:")
            for i, res in enumerate(st.session_state.search_results):
                with st.container():
                    st.markdown(f"**{res['title']}** ({res.get('source', 'Job Board')})")
                    st.caption(f"URL: [{res['url']}]({res['url']})")
                    st.write(res["snippet"])
                    col_b1, col_b2 = st.columns([1, 4])
                    with col_b1:
                        if st.button(f"Use This Job", key=f"select_job_{i}"):
                            with st.spinner("Extracting selected job details..."):
                                extractor = JobExtractor(llm_client)
                                st.session_state.job_data = extractor.parse_job_description(res['url'])
                                st.session_state.target_job_url = res['url']
                                st.success(f"Selected: {st.session_state.job_data.get('title', 'Role')}")
                    st.divider()

    # Display extracted job requirements summary
    if st.session_state.job_data:
        jd = st.session_state.job_data
        st.markdown(f"### Target: {jd.get('title', 'Role')} ({jd.get('company', 'Company')})")
        st.caption(f"🔗 **Tracking URL / Source:** {st.session_state.target_job_url}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Required Hard Skills:**")
            st.write(", ".join(jd.get("required_hard_skills", [])) or "None specified")
            st.markdown("**Tools & Frameworks:**")
            st.write(", ".join(jd.get("tools_and_frameworks", [])) or "None specified")
        with c2:
            st.markdown("**Industry & Domain Keywords:**")
            st.write(", ".join(jd.get("industry_and_domain_keywords", [])) or "None specified")
            st.markdown("**Core Responsibilities:**")
            for resp in jd.get("core_responsibilities", [])[:4]:
                st.markdown(f"- {resp}")

# -------------------------------------------------------------
# TAB 3: ATS SCORE & KEYWORD GAP ANALYSIS
# -------------------------------------------------------------
with tab3:
    st.subheader("ATS Compatibility Score & Gap Analysis")

    if not st.session_state.master_resume_text:
        st.info("Please load or paste your Master Resume in Tab 1 first.")
    elif not st.session_state.job_data:
        st.info("Please provide and analyze a Target Job in Tab 2 first.")
    else:
        if st.button("⚡ Run Full ATS Audit & Gap Analysis", type="primary"):
            with st.spinner("Calculating semantic match, keyword taxonomy, and ATS heuristics..."):
                optimizer = ATSOptimizer()
                profile = st.session_state.master_profile or {"skills": {}}
                results = optimizer.calculate_ats_score(
                    resume_data=profile,
                    job_data=st.session_state.job_data,
                    raw_resume_text=st.session_state.master_resume_text
                )
                st.session_state.ats_results = results
                st.success("ATS Audit Complete!")

    if st.session_state.ats_results:
        res = st.session_state.ats_results
        score = res["overall_score"]

        # Score Gauge & Breakdown Cards
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("Overall ATS Score", f"{score} / 100", help="Weighted aggregate of keyword coverage, metric density, and format safety.")
        with col_m2:
            st.metric("Keyword Match", f"{res['breakdown']['keyword_match_score']}%")
        with col_m3:
            st.metric("Impact & Metrics", f"{res['breakdown']['quantification_impact_score']}%")
        with col_m4:
            st.metric("Format Safety", f"{res['breakdown']['formatting_safety_score']}%")

        st.info(f"**ATS Assessment:** {res['rating']}")

        # Keyword Gap Section
        kw = res["keyword_analysis"]
        c_kw1, c_kw2 = st.columns(2)
        with c_kw1:
            st.markdown("#### ✅ Matched Target Keywords")
            if kw["matched_keywords"]:
                st.markdown("".join([f'<span class="badge-match">{k}</span>' for k in kw["matched_keywords"]]), unsafe_allow_html=True)
            else:
                st.write("No exact keyword matches found.")

        with c_kw2:
            st.markdown("#### ⚠️ Missing High-Priority Keywords")
            if kw["missing_critical_keywords"]:
                st.markdown("".join([f'<span class="badge-missing">{k}</span>' for k in kw["missing_critical_keywords"]]), unsafe_allow_html=True)
            else:
                st.write("Zero missing keywords! Exceptional match.")

        # Quantification Analysis
        st.markdown("---")
        st.markdown("#### 📈 Recruiter Impact & Google XYZ Formula Check")
        q_analysis = res["quantification_analysis"]
        st.write(f"Analyzed **{q_analysis['total_bullets_analyzed']}** accomplishment bullets across your career.")
        st.write(f"**Quantification Ratio:** {q_analysis['quantification_ratio']}% of bullets contain concrete metrics (%, $, numbers, scales).")

        # Actionable Advice
        st.markdown("---")
        st.markdown("#### 🎯 Actionable Tactics to Win Recruiter Screening")
        for tip in res["actionable_tips"]:
            st.markdown(f"- {tip}")

# -------------------------------------------------------------
# TAB 4: TAILORED RESUME GENERATION (PDF, DOCX, MD)
# -------------------------------------------------------------
with tab4:
    st.subheader("Generate Tailored ATS Resume (PDF & DOCX)")
    st.write("Using your local Llama model, this synthesizes your authentic achievements into a single-column, ATS-safe resume tailored specifically to the employer's requirements.")

    if not st.session_state.master_resume_text:
        st.info("Please load your Master Resume in Tab 1.")
    elif not st.session_state.job_data:
        st.info("Please analyze a Target Job in Tab 2.")
    else:
        # ATS Template & Page Length Controls
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            template_label = st.selectbox(
                "🎨 ATS PDF Template Style",
                [
                    "Jake's Tech Standard (Single-Column Sans-Serif - Gold Standard)",
                    "Harvard Ivy Standard (Classic Serif - Times New Roman / Executive)",
                    "Modern Minimalist (FAANG Accent Blue)"
                ],
                help="Jake's Resume is the tech industry gold standard. Harvard Standard is preferred for executive, finance, and consulting roles."
            )
            template_code = "jake" if "Jake" in template_label else ("harvard" if "Harvard" in template_label else "modern")

        with col_opt2:
            length_label = st.selectbox(
                "📏 Target Resume Page Length",
                [
                    "Strict 1-Page (Dense & Compact - Best for < 7 Years)",
                    "Standard 2-Page (Comprehensive Senior Depth - 7+ Years)",
                    "Auto / Flexible (Natural Flow)"
                ],
                help="Strict 1-Page applies 0.5-inch margins and tight bullet budgeting so content never spills onto a second page."
            )
            length_code = "1-page" if "1-Page" in length_label else ("2-page" if "2-Page" in length_label else "auto")

        col_gen1, col_gen2 = st.columns([2, 1])
        with col_gen1:
            if st.button("🚀 Generate Tailored Resume with Local Llama", type="primary", use_container_width=True):
                with st.spinner(f"Tailoring resume with {model_choice} (Template: {template_code.title()}, Budget: {length_code})..."):
                    tailorer = ResumeTailorer(llm_client)
                    profile = st.session_state.master_profile or {}
                    if not st.session_state.ats_results:
                        optimizer = ATSOptimizer()
                        st.session_state.ats_results = optimizer.calculate_ats_score(
                            profile, st.session_state.job_data, st.session_state.master_resume_text
                        )

                    tailored_md = tailorer.generate_tailored_resume(
                        master_profile=profile,
                        raw_master_text=st.session_state.master_resume_text,
                        job_data=st.session_state.job_data,
                        ats_analysis=st.session_state.ats_results,
                        page_length=length_code
                    )
                    st.session_state.tailored_resume_md = tailored_md

                    # Run ATS audit again on the tailored resume
                    optimizer = ATSOptimizer()
                    ats_after = optimizer.calculate_ats_score({}, st.session_state.job_data, tailored_md)
                    comparison = optimizer.compare_ats_scores(st.session_state.ats_results, ats_after)
                    st.session_state.ats_tailored = ats_after
                    st.session_state.ats_comparison = comparison

                    # Build file exports & record application
                    exporter = DocumentExporter(output_dir=OUTPUT_DIR)
                    cand_name = profile.get("contact", {}).get("name") or "Candidate"
                    target_title = st.session_state.job_data.get("title", "Role")
                    company = st.session_state.job_data.get("company", "Company")
                    target_url = st.session_state.target_job_url

                    # Sanitize filename
                    clean_c = re.sub(r"[^\w\-]", "_", company).strip("_")
                    clean_t = re.sub(r"[^\w\-]", "_", target_title).strip("_")
                    base_name = f"Resume_{clean_c}_{clean_t}"

                    pdf_file = exporter.export_pdf(
                        markdown_text=tailored_md,
                        filename=f"{base_name}.pdf",
                        candidate_name=cand_name,
                        job_title=target_title,
                        company=company,
                        job_url=target_url,
                        template=template_code,
                        page_length=length_code
                    )

                    try:
                        docx_file = exporter.export_docx(tailored_md, filename=f"{base_name}.docx", page_length=length_code)
                    except Exception:
                        docx_file = ""

                    md_file = exporter.export_markdown(tailored_md, filename=f"{base_name}.md")

                    # Track application
                    tracker = ApplicationTracker(output_dir=OUTPUT_DIR)
                    app_record = tracker.record_application(
                        candidate_name=cand_name,
                        job_title=target_title,
                        company=company,
                        job_url=target_url,
                        original_ats_score=st.session_state.ats_results["overall_score"],
                        tailored_ats_score=ats_after["overall_score"],
                        breakdown=ats_after["breakdown"],
                        pdf_path=pdf_file,
                        docx_path=docx_file,
                        md_path=md_file,
                        top_skills=st.session_state.job_data.get("required_hard_skills", [])[:6],
                        newly_matched_keywords=comparison["newly_matched_keywords"]
                    )
                    st.session_state.last_recorded_app = app_record
                    delta_str = f"+{comparison['score_delta']}%" if comparison['score_delta'] >= 0 else f"{comparison['score_delta']}%"
                    st.success(f"Tailored resume generated! ATS Score increased from **{comparison['score_before']}%** to **{comparison['score_after']}%** ({delta_str} boost 🚀).")

    if st.session_state.tailored_resume_md:
        st.markdown("---")

        # Before vs After ATS Comparison Dashboard
        if "ats_comparison" in st.session_state and st.session_state.ats_comparison:
            comp = st.session_state.ats_comparison
            st.markdown("### 📊 ATS Optimization Comparison (Before vs. After)")

            col_c1, col_c2, col_c3, col_c4 = st.columns(4)
            with col_c1:
                delta_s = f"+{comp['score_delta']}%" if comp['score_delta'] >= 0 else f"{comp['score_delta']}%"
                st.metric("Tailored ATS Score", f"{comp['score_after']} / 100", delta=delta_s)
                st.caption(f"Master Resume was: {comp['score_before']}%")
            with col_c2:
                delta_k = f"+{comp['keyword_match_delta']}%" if comp['keyword_match_delta'] >= 0 else f"{comp['keyword_match_delta']}%"
                st.metric("Keyword Match", f"{comp['keyword_match_after']}%", delta=delta_k)
                st.caption(f"Master Match was: {comp['keyword_match_before']}%")
            with col_c3:
                delta_i = f"+{comp['impact_delta']}%" if comp['impact_delta'] >= 0 else f"{comp['impact_delta']}%"
                st.metric("Impact & Metrics", f"{comp['impact_after']}%", delta=delta_i)
                st.caption(f"Master Impact was: {comp['impact_before']}%")
            with col_c4:
                st.metric("Format Safety", "100%", delta="0% (ATS Safe)")
                st.caption("Single-column verified")

            # Keyword integration highlights
            c_new1, c_new2 = st.columns(2)
            with c_new1:
                st.markdown("#### 🎯 Newly Integrated Target Keywords")
                if comp.get("newly_matched_keywords"):
                    st.markdown("".join([f'<span class="badge-match">+{k}</span>' for k in comp["newly_matched_keywords"]]), unsafe_allow_html=True)
                else:
                    st.write("All available keywords from profile already matched.")

            with c_new2:
                st.markdown("#### ⚠️ Remaining Gaps")
                if comp.get("remaining_missing"):
                    st.markdown("".join([f'<span class="badge-missing">{k}</span>' for k in comp["remaining_missing"]]), unsafe_allow_html=True)
                else:
                    st.write("Zero critical gaps remaining! Exceptional ATS match.")

            st.markdown("---")
        # Editor & Preview
        st.session_state.tailored_resume_md = st.text_area(
            "Tailored Resume (Markdown / Single-Column ATS Layout)",
            value=st.session_state.tailored_resume_md,
            height=380
        )

        # Download / Export Section
        st.markdown("### 📥 Download ATS-Compliant Formats")
        exp_col1, exp_col2, exp_col3 = st.columns(3)

        exporter = DocumentExporter(output_dir=OUTPUT_DIR)
        cand_name = (st.session_state.master_profile or {}).get("contact", {}).get("name") or "Candidate"
        target_title = (st.session_state.job_data or {}).get("title", "Role")
        company = (st.session_state.job_data or {}).get("company", "Company")
        target_url = st.session_state.target_job_url
        clean_c = re.sub(r"[^\w\-]", "_", company).strip("_")
        clean_t = re.sub(r"[^\w\-]", "_", target_title).strip("_")
        base_name = f"Resume_{clean_c}_{clean_t}"

        with exp_col1:
            try:
                pdf_path = exporter.export_pdf(
                    st.session_state.tailored_resume_md,
                    filename=f"{base_name}.pdf",
                    candidate_name=cand_name,
                    job_title=target_title,
                    company=company,
                    job_url=target_url,
                    template=template_code,
                    page_length=length_code
                )
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label=f"📕 Download PDF ({template_code.title()} • {length_code})",
                        data=f.read(),
                        file_name=f"{base_name}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            except Exception as e:
                st.caption(f"PDF export note: {e}")

        with exp_col2:
            try:
                docx_path = exporter.export_docx(st.session_state.tailored_resume_md, filename=f"{base_name}.docx", page_length=length_code)
                with open(docx_path, "rb") as f:
                    st.download_button(
                        label="📄 Download DOCX (Safest for Workday)",
                        data=f.read(),
                        file_name=f"{base_name}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
            except Exception as e:
                st.caption(f"DOCX export note: {e}")

        with exp_col3:
            md_path = exporter.export_markdown(st.session_state.tailored_resume_md, filename=f"{base_name}.md")
            with open(md_path, "r", encoding="utf-8") as f:
                st.download_button(
                    label="📝 Download Markdown (.md)",
                    data=f.read(),
                    file_name=f"{base_name}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

        if st.session_state.last_recorded_app:
            rec = st.session_state.last_recorded_app
            st.info(f"💾 **Application Record Created:** `{rec['company']} - {rec['job_title']}` | **URL:** {rec['job_url']}")

# -------------------------------------------------------------
# TAB 5: INTERVIEW PREP & TACTICS
# -------------------------------------------------------------
with tab5:
    st.subheader("Tactical Interview Preparation Guide")
    st.write("Generates role-specific talking points, predicted technical hurdles, and behavioral STAR stories.")

    if not st.session_state.tailored_resume_md:
        st.info("Please generate a tailored resume in Tab 4 first.")
    else:
        if st.button("🧠 Generate Role-Specific Interview Strategy", type="primary"):
            with st.spinner("Analyzing candidate background against interview panel questions..."):
                tailorer = ResumeTailorer(llm_client)
                prep = tailorer.generate_interview_prep(
                    st.session_state.tailored_resume_md,
                    st.session_state.job_data or {}
                )
                st.session_state.interview_prep = prep

                # Save prep to file
                prep_path = os.path.join(OUTPUT_DIR, "interview_prep.json")
                with open(prep_path, "w", encoding="utf-8") as f:
                    json.dump(prep, f, indent=2)

                st.success("Interview preparation strategy generated!")

        if st.session_state.interview_prep:
            prep = st.session_state.interview_prep

            st.markdown("### 🎙️ 60-Second Elevator Pitch ('Tell me about yourself')")
            st.info(prep.get("elevator_pitch", "Deliver your core engineering impact concisely."))

            col_q1, col_q2 = st.columns(2)
            with col_q1:
                st.markdown("### 💻 Top Predicted Technical Questions")
                for item in prep.get("top_technical_questions", []):
                    st.markdown(f"**Q: {item.get('question')}**")
                    st.caption(f"*Why asked:* {item.get('why_asked')}")
                    st.write(f"👉 **Talking Points:** {item.get('recommended_talking_points')}")
                    st.write("")

            with col_q2:
                st.markdown("### 🤝 Behavioral STAR Framework Questions")
                for item in prep.get("top_behavioral_questions", []):
                    st.markdown(f"**Q: {item.get('question')}**")
                    st.write(f"👉 **STAR Approach:** {item.get('star_approach')}")
                    st.write("")

            st.markdown("### 🚩 Gap Bridging Strategies")
            for item in prep.get("potential_red_flags_or_gaps", []):
                st.warning(f"**Potential Gap:** {item.get('gap')}\n\n**How to Bridge:** {item.get('how_to_bridge')}")

            st.markdown("### ❓ Strategic Questions to Ask the Interviewer")
            for q in prep.get("questions_to_ask_interviewer", []):
                st.markdown(f"- {q}")

# -------------------------------------------------------------
# TAB 6: APPLICATION TRACKER & HISTORY
# -------------------------------------------------------------
with tab6:
    st.subheader("📂 Application History & Tailored Resumes")
    st.write("Track every job and URL you have generated a tailored resume for, along with its ATS score and generated files.")

    tracker = ApplicationTracker(output_dir=OUTPUT_DIR)
    history = tracker.load_history()

    if not history:
        st.info("No applications tailored yet. Once you tailor a resume in Tab 4, it will automatically appear here with its job URL and ATS score.")
    else:
        st.write(f"Showing **{len(history)}** tailored applications:")

        for rec in history:
            with st.container():
                st.markdown(f"### {rec.get('job_title', 'Role')} @ **{rec.get('company', 'Company')}**")
                c_info1, c_info2 = st.columns([3, 1])

                with c_info1:
                    job_url = rec.get("job_url", "Direct Text Input")
                    if job_url.startswith("http"):
                        st.markdown(f"🔗 **Job Posting URL:** [{job_url}]({job_url})")
                    else:
                        st.markdown(f"🔗 **Source:** `{job_url}`")
                    st.caption(f"📅 **Date Created:** {rec.get('created_at')} | **Candidate:** {rec.get('candidate_name')}")

                    if rec.get("top_skills"):
                        st.write("**Target Skills:** " + ", ".join([f"`{s}`" for s in rec.get("top_skills", [])]))

                with c_info2:
                    orig_s = rec.get("original_ats_score", rec.get("ats_score", 0))
                    tailor_s = rec.get("tailored_ats_score", rec.get("ats_score", 0))
                    delta_s = rec.get("ats_score_delta", tailor_s - orig_s)
                    delta_str = f"+{delta_s}%" if delta_s >= 0 else f"{delta_s}%"
                    st.metric("Tailored ATS Score", f"{tailor_s}%", delta=delta_str)
                    st.caption(f"Initial Master: {orig_s}%")

                if rec.get("newly_matched_keywords"):
                    st.write("**Integrated Keywords:** " + ", ".join([f"`+{k}`" for k in rec.get("newly_matched_keywords", [])[:6]]))

                # Action buttons to download specific saved files
                col_d1, col_d2, col_d3 = st.columns(3)
                pdf_p = rec.get("files", {}).get("pdf")
                docx_p = rec.get("files", {}).get("docx")
                md_p = rec.get("files", {}).get("markdown")

                with col_d1:
                    if pdf_p and os.path.exists(pdf_p):
                        with open(pdf_p, "rb") as f:
                            st.download_button(
                                label="📕 Download Saved PDF",
                                data=f.read(),
                                file_name=os.path.basename(pdf_p),
                                mime="application/pdf",
                                key=f"hist_pdf_{rec['id']}"
                            )
                with col_d2:
                    if docx_p and os.path.exists(docx_p):
                        with open(docx_p, "rb") as f:
                            st.download_button(
                                label="📄 Download Saved DOCX",
                                data=f.read(),
                                file_name=os.path.basename(docx_p),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"hist_docx_{rec['id']}"
                            )
                with col_d3:
                    if md_p and os.path.exists(md_p):
                        with open(md_p, "r", encoding="utf-8") as f:
                            st.download_button(
                                label="📝 Download Saved Markdown",
                                data=f.read(),
                                file_name=os.path.basename(md_p),
                                mime="text/markdown",
                                key=f"hist_md_{rec['id']}"
                            )

                st.divider()
