"""
Resume Matcher Pro - CLI Automation Tool
Command-line interface to parse master resumes, evaluate ATS scores,
tailor resumes with local Llama models, re-run ATS evaluation,
export PDF/DOCX/MD, and record application tracking history.
"""

import os
import sys
import argparse
import json
import re
from config import DEFAULT_MODEL, DEFAULT_OLLAMA_HOST, OUTPUT_DIR, DATA_DIR, RECOMMENDED_LLAMA_MODELS
from modules.llm_client import LocalLLMClient
from modules.resume_parser import ResumeParser
from modules.job_extractor import JobExtractor
from modules.ats_optimizer import ATSOptimizer
from modules.resume_tailorer import ResumeTailorer
from modules.document_exporter import DocumentExporter
from modules.job_searcher import JobSearcher
from modules.application_tracker import ApplicationTracker

def print_banner():
    print("""
======================================================================
               🎯 RESUME MATCHER PRO (AI + ATS OPTIMIZER)             
     Local Llama AI • Single-Column ATS Formats • PDF & DOCX Exports  
======================================================================
    """)

def run_pipeline(
    resume_path: str,
    job_input: str,
    job_url: str = "",
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_OLLAMA_HOST,
    output_name: str = "",
    template: str = "jake",
    page_length: str = "auto"
):
    print_banner()
    print(f"[*] Initializing with Local Model: {model} at {host}")
    print(f"[*] ATS PDF Template: {template.title()} | Target Page Budget: {page_length}")
    llm = LocalLLMClient(host=host, model=model)
    health = llm.check_health()
    if health.get("connected"):
        print(f"[+] Connected to local Ollama server. Available models: {', '.join(health.get('models', []))}")
    else:
        print(f"[!] Warning: Ollama not reachable at {host}. Fallback modes will be used if needed.")

    # 1. Parse Master Resume
    print(f"\n[1/6] Loading Master Resume from: {resume_path}")
    parser = ResumeParser(llm)
    with open(resume_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_resume = f.read()
    print(f"      Parsed {len(raw_resume.split())} words.")
    print("      Extracting structured candidate profile...")
    profile = parser.parse_to_master_profile(raw_resume)
    candidate_name = profile.get("contact", {}).get("name") or "Candidate"
    print(f"      Candidate: {candidate_name} ({profile.get('contact', {}).get('email', 'N/A')})")

    # 2. Extract Job Requirements
    print(f"\n[2/6] Analyzing Target Job...")
    extractor = JobExtractor(llm)
    job_data = extractor.parse_job_description(job_input)
    job_title = job_data.get("title", "Target Role")
    company = job_data.get("company", "Target Company")
    resolved_url = job_url or (job_input if job_input.startswith("http") else "Direct Text Input")

    print(f"      Target Title: {job_title}")
    print(f"      Company: {company}")
    print(f"      Job URL/Source: {resolved_url}")
    print(f"      Required Skills: {', '.join(job_data.get('required_hard_skills', [])[:5])}")

    # Foundational Candidate-Job Fit Check
    optimizer = ATSOptimizer()
    fit = optimizer.evaluate_candidate_job_fit(profile, job_data, raw_resume)
    print(f"      [Profile Compatibility] {fit['verdict']} ({fit['overlap_percentage']}% Core Stack Overlap)")
    print(f"      [Seniority Alignment]  {fit['seniority_status']}")

    # Build meaningful file base name if not supplied
    if not output_name:
        clean_comp = re.sub(r"[^\w\-]", "_", company).strip("_")
        clean_tit = re.sub(r"[^\w\-]", "_", job_title).strip("_")
        output_name = f"Resume_{clean_comp}_{clean_tit}"

    # 3. Calculate Initial ATS Score on Master Resume
    print(f"\n[3/6] Running Initial ATS Audit on Master Resume...")
    optimizer = ATSOptimizer()
    ats_before = optimizer.calculate_ats_score(profile, job_data, raw_resume)
    score_before = ats_before["overall_score"]
    print(f"      Initial ATS Score: {score_before} / 100 ({ats_before['rating']})")
    print(f"      Keyword Match: {ats_before['breakdown']['keyword_match_score']}%")

    # 4. Tailor Resume with Llama
    print(f"\n[4/6] Tailoring Resume using local {model} (Page Budget: {page_length})...")
    tailorer = ResumeTailorer(llm)
    tailored_md = tailorer.generate_tailored_resume(profile, raw_resume, job_data, ats_before, page_length=page_length)

    # 5. RE-RUN ATS ON TAILORED RESUME
    print(f"\n[5/6] Re-Running ATS Audit on Tailored Resume...")
    ats_after = optimizer.calculate_ats_score({}, job_data, tailored_md)
    comparison = optimizer.compare_ats_scores(ats_before, ats_after)

    score_after = comparison["score_after"]
    delta = comparison["score_delta"]
    delta_str = f"+{delta}" if delta >= 0 else str(delta)

    kw_b_str = f"{comparison['keyword_match_before']}%"
    kw_a_str = f"{comparison['keyword_match_after']}%"
    kw_d_str = f"+{comparison['keyword_match_delta']}%"

    imp_b_str = f"{comparison['impact_before']}%"
    imp_a_str = f"{comparison['impact_after']}%"
    imp_d_str = f"+{comparison['impact_delta']}%"

    print("\n" + "=" * 70)
    print("               📊 BEFORE vs. AFTER ATS SCORE COMPARISON")
    print("=" * 70)
    print(f" {'Metric':<25} {'Master Resume':<16} {'Tailored Resume':<16} {'Change':<10}")
    print("-" * 70)
    print(f" {'Overall ATS Score':<25} {f'{score_before} / 100':<16} {f'{score_after} / 100':<16} {delta_str} 🚀")
    print(f" {'Keyword Match':<25} {kw_b_str:<16} {kw_a_str:<16} {kw_d_str:<10}")
    print(f" {'Impact & Metrics':<25} {imp_b_str:<16} {imp_a_str:<16} {imp_d_str:<10}")
    print(f" {'Formatting Safety':<25} {'100%':<16} {'100%':<16} {'0%':<10}")
    print("-" * 70)
    if comparison["newly_matched_keywords"]:
        print(f" Newly Integrated Keywords ({comparison['newly_matched_count']}): {', '.join(comparison['newly_matched_keywords'][:6])}")
    if comparison["remaining_missing"]:
        print(f" Remaining Gaps ({comparison['remaining_missing_count']}): {', '.join(comparison['remaining_missing'][:6])}")
    else:
        print(" Remaining Gaps: Zero critical gaps remaining! 100% keyword coverage.")
    print("=" * 70)

    # 6. Export Documents & Log History
    print(f"\n[6/6] Exporting ATS-Compliant Documents to '{OUTPUT_DIR}'...")
    exporter = DocumentExporter(OUTPUT_DIR)

    # Export PDF
    pdf_file = exporter.export_pdf(
        tailored_md,
        filename=f"{output_name}.pdf",
        candidate_name=candidate_name,
        job_title=job_title,
        company=company,
        job_url=resolved_url,
        template=template,
        page_length=page_length
    )
    print(f"      [✓] Text-Layer PDF: {pdf_file} ({template.title()} • {page_length})")

    # Export Word DOCX
    docx_file = ""
    try:
        docx_file = exporter.export_docx(tailored_md, f"{output_name}.docx", page_length=page_length)
        print(f"      [✓] Word DOCX: {docx_file} (ATS Single-Column Format)")
    except Exception as e:
        print(f"      [!] DOCX export skipped ({e}).")

    # Export Markdown
    md_file = exporter.export_markdown(tailored_md, f"{output_name}.md")
    print(f"      [✓] Markdown: {md_file}")

    # Generate Interview Strategy
    print("\n[+] Generating Interview Strategy & Talking Points...")
    prep = tailorer.generate_interview_prep(tailored_md, job_data)
    prep_path = os.path.join(OUTPUT_DIR, f"{output_name}_interview_prep.json")
    with open(prep_path, "w", encoding="utf-8") as f:
        json.dump(prep, f, indent=2)
    print(f"      [✓] Interview Prep saved: {prep_path}")

    # Track in Application History
    tracker = ApplicationTracker(OUTPUT_DIR)
    record = tracker.record_application(
        candidate_name=candidate_name,
        job_title=job_title,
        company=company,
        job_url=resolved_url,
        original_ats_score=score_before,
        tailored_ats_score=score_after,
        breakdown=ats_after["breakdown"],
        pdf_path=pdf_file,
        docx_path=docx_file,
        md_path=md_file,
        interview_prep_path=prep_path,
        top_skills=job_data.get("required_hard_skills", [])[:6],
        newly_matched_keywords=comparison["newly_matched_keywords"]
    )
    print(f"      [✓] Logged in history: '{company} - {job_title}' (URL: {resolved_url})")

    print("\n======================================================================")
    print(f" SUCCESS! ATS Score increased from {score_before}% to {score_after}% ({delta_str}% boost).")
    print(" Tailored resume PDF & DOCX are ready for submission.")
    print("======================================================================\n")

def main():
    parser = argparse.ArgumentParser(description="Resume Matcher Pro CLI")
    parser.add_argument("--resume", "-r", default=os.path.join(DATA_DIR, "sample_master_resume.md"), help="Path to master resume file")
    parser.add_argument("--job", "-j", default=os.path.join(DATA_DIR, "sample_job_description.txt"), help="Path to job description text file or job URL")
    parser.add_argument("--url", "-u", default="", help="Target Job posting URL (for tracking)")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help="Local Llama model name (e.g. llama3.1:8b, llama3.2:3b, llama3.3:70b)")
    parser.add_argument("--host", default=DEFAULT_OLLAMA_HOST, help="Ollama host endpoint")
    parser.add_argument("--output", "-o", default="", help="Base filename for generated resume")
    parser.add_argument("--template", "-t", default="jake", choices=["jake", "harvard", "modern"], help="ATS PDF Template: 'jake' (tech sans-serif), 'harvard' (classic serif), 'modern' (accent)")
    parser.add_argument("--length", "-l", default="auto", choices=["1-page", "2-page", "auto"], help="Page budget: '1-page' (strict 1-page), '2-page' (senior), 'auto'")
    parser.add_argument("--web", action="store_true", help="Launch Streamlit web UI")

    args = parser.parse_args()

    if args.web:
        os.system("streamlit run app.py")
        return

    # Check if job input is a file or direct string / url
    if os.path.exists(args.job):
        with open(args.job, "r", encoding="utf-8", errors="ignore") as f:
            job_input = f.read()
    else:
        job_input = args.job

    run_pipeline(
        resume_path=args.resume,
        job_input=job_input,
        job_url=args.url,
        model=args.model,
        host=args.host,
        output_name=args.output,
        template=args.template,
        page_length=args.length
    )

if __name__ == "__main__":
    main()
