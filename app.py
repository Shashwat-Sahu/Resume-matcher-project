"""
Resume Matcher Pro - Streamlit Web Application
Connects to local Llama models via Ollama to tailor master resumes,
beat ATS screening filters, and win interviews.
"""

import os
import json
import streamlit as st
from config import RECOMMENDED_LLAMA_MODELS, DEFAULT_MODEL, DEFAULT_OLLAMA_HOST, OUTPUT_DIR, DATA_DIR
from modules.llm_client import LocalLLMClient
from modules.resume_parser import ResumeParser
from modules.job_extractor import JobExtractor
from modules.ats_optimizer import ATSOptimizer
from modules.resume_tailorer import ResumeTailorer
from modules.document_exporter import DocumentExporter
from modules.job_searcher import JobSearcher

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
    .score-card {
        padding: 1.2rem;
        border-radius: 10px;
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        text-align: center;
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
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "master_resume_text" not in st.session_state:
    st.session_state.master_resume_text = ""
if "master_profile" not in st.session_state:
    st.session_state.master_profile = None
if "job_data" not in st.session_state:
    st.session_state.job_data = None
if "ats_results" not in st.session_state:
    st.session_state.ats_results = None
if "tailored_resume_md" not in st.session_state:
    st.session_state.tailored_resume_md = ""
if "interview_prep" not in st.session_state:
    st.session_state.interview_prep = None

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
st.markdown('<div class="sub-title">Connects to local Llama models to tailor your Master Resume for any target role, pass ATS filters, and land interviews.</div>', unsafe_allow_html=True)

# Main Application Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1. 📄 Master Resume",
    "2. 💼 Target Job Intake",
    "3. 📊 ATS Score & Gap Analysis",
    "4. ✨ Tailored Resume",
    "5. 🎙️ Interview Prep"
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
    st.write("Provide the job you want to match against via direct text, a live posting link, or automated job search.")

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

        if st.button("Analyze Target Job", type="primary"):
            if not jd_text.strip():
                st.warning("Please paste a job description.")
            else:
                with st.spinner("Extracting employer requirements and keywords..."):
                    extractor = JobExtractor(llm_client)
                    st.session_state.job_data = extractor.parse_job_description(jd_text)
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
                                st.success(f"Selected: {st.session_state.job_data.get('title', 'Role')}")
                    st.divider()

    # Display extracted job requirements summary
    if st.session_state.job_data:
        jd = st.session_state.job_data
        st.markdown(f"### Target: {jd.get('title', 'Role')} ({jd.get('company', 'Company')})")
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
# TAB 4: TAILORED RESUME GENERATION
# -------------------------------------------------------------
with tab4:
    st.subheader("Generate Tailored, ATS-Optimized Resume")
    st.write("Using your local Llama model, this synthesizes your authentic achievements into a single-column, ATS-safe resume tailored specifically to the employer's requirements.")

    if not st.session_state.master_resume_text:
        st.info("Please load your Master Resume in Tab 1.")
    elif not st.session_state.job_data:
        st.info("Please analyze a Target Job in Tab 2.")
    else:
        col_gen1, col_gen2 = st.columns([2, 1])
        with col_gen1:
            if st.button("🚀 Generate Tailored Resume with Local Llama", type="primary", use_container_width=True):
                with st.spinner(f"Tailoring resume with {model_choice}..."):
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
                        ats_analysis=st.session_state.ats_results
                    )
                    st.session_state.tailored_resume_md = tailored_md
                    st.success("Resume tailored successfully!")

    if st.session_state.tailored_resume_md:
        st.markdown("---")
        # Editor & Preview
        st.session_state.tailored_resume_md = st.text_area(
            "Tailored Resume (Markdown / Single-Column ATS Layout)",
            value=st.session_state.tailored_resume_md,
            height=420
        )

        # Download / Export Section
        st.markdown("### 📥 Download ATS-Compliant Formats")
        exp_col1, exp_col2, exp_col3 = st.columns(3)

        exporter = DocumentExporter(output_dir=OUTPUT_DIR)

        with exp_col1:
            try:
                docx_path = exporter.export_docx(st.session_state.tailored_resume_md, filename="ATS_Tailored_Resume.docx")
                with open(docx_path, "rb") as f:
                    st.download_button(
                        label="📄 Download DOCX (Safest for Workday)",
                        data=f.read(),
                        file_name="ATS_Tailored_Resume.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
            except Exception as e:
                st.caption(f"DOCX export requires python-docx ({e})")

        with exp_col2:
            md_path = exporter.export_markdown(st.session_state.tailored_resume_md, filename="ATS_Tailored_Resume.md")
            with open(md_path, "r", encoding="utf-8") as f:
                st.download_button(
                    label="📝 Download Markdown (.md)",
                    data=f.read(),
                    file_name="ATS_Tailored_Resume.md",
                    mime="text/markdown",
                    use_container_width=True
                )

        with exp_col3:
            st.download_button(
                label="📋 Download Plain Text (.txt)",
                data=st.session_state.tailored_resume_md,
                file_name="ATS_Tailored_Resume.txt",
                mime="text/plain",
                use_container_width=True
            )

        # Re-Audit Button on Tailored Resume
        st.markdown("---")
        if st.button("🔄 Re-Audit ATS Score on Tailored Resume"):
            with st.spinner("Re-auditing tailored resume..."):
                optimizer = ATSOptimizer()
                new_results = optimizer.calculate_ats_score(
                    resume_data={},
                    job_data=st.session_state.job_data,
                    raw_resume_text=st.session_state.tailored_resume_md
                )
                st.session_state.ats_results = new_results
                st.success(f"New ATS Score: **{new_results['overall_score']} / 100** ({new_results['rating']})")

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
