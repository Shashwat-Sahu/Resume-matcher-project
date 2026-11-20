"""
Resume Matcher Pro - CLI Automation Tool
Command-line interface to parse master resumes, evaluate ATS scores,
tailor resumes with local Llama models, and export ATS-compliant formats.
"""

import os
import sys
import argparse
import json
from config import DEFAULT_MODEL, DEFAULT_OLLAMA_HOST, OUTPUT_DIR, DATA_DIR, RECOMMENDED_LLAMA_MODELS
from modules.llm_client import LocalLLMClient
from modules.resume_parser import ResumeParser
from modules.job_extractor import JobExtractor
from modules.ats_optimizer import ATSOptimizer
from modules.resume_tailorer import ResumeTailorer
from modules.document_exporter import DocumentExporter
from modules.job_searcher import JobSearcher

def print_banner():
    print("""
======================================================================
               🎯 RESUME MATCHER PRO (AI + ATS OPTIMIZER)             
     Local Llama AI • Single-Column ATS Formats • Recruiter Strategy  
======================================================================
    """)

def run_pipeline(resume_path: str, job_input: str, model: str = DEFAULT_MODEL, host: str = DEFAULT_OLLAMA_HOST, output_name: str = "tailored_resume"):
    print_banner()
    print(f"[*] Initializing with Local Model: {model} at {host}")
    llm = LocalLLMClient(host=host, model=model)
    health = llm.check_health()
    if health.get("connected"):
        print(f"[+] Connected to local Ollama server. Available models: {', '.join(health.get('models', []))}")
    else:
        print(f"[!] Warning: Ollama not reachable at {host}. Fallback modes will be used if needed.")

    # 1. Parse Master Resume
    print(f"\n[1/5] Loading Master Resume from: {resume_path}")
    parser = ResumeParser(llm)
    with open(resume_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_resume = f.read()
    print(f"      Parsed {len(raw_resume.split())} words.")
    print("      Extracting structured candidate profile...")
    profile = parser.parse_to_master_profile(raw_resume)
    print(f"      Candidate: {profile.get('contact', {}).get('name', 'N/A')} ({profile.get('contact', {}).get('email', 'N/A')})")

    # 2. Extract Job Requirements
    print(f"\n[2/5] Analyzing Target Job...")
    extractor = JobExtractor(llm)
    job_data = extractor.parse_job_description(job_input)
    print(f"      Target Title: {job_data.get('title', 'Role')}")
    print(f"      Required Skills: {', '.join(job_data.get('required_hard_skills', [])[:5])}")

    # 3. Calculate ATS Score & Gap
    print(f"\n[3/5] Computing ATS Compatibility & Keyword Gap Analysis...")
    optimizer = ATSOptimizer()
    ats_res = optimizer.calculate_ats_score(profile, job_data, raw_resume)
    score = ats_res["overall_score"]
    print(f"      ---------------------------------------------")
    print(f"      OVERALL ATS COMPATIBILITY SCORE: {score} / 100")
    print(f"      Rating: {ats_res['rating']}")
    print(f"      Keyword Match: {ats_res['breakdown']['keyword_match_score']}%")
    print(f"      Impact & Metrics: {ats_res['breakdown']['quantification_impact_score']}%")
    print(f"      Formatting Safety: {ats_res['breakdown']['formatting_safety_score']}%")
    print(f"      ---------------------------------------------")
    kw = ats_res["keyword_analysis"]
    print(f"      Matched Keywords ({kw['matched_count']}): {', '.join(kw['matched_keywords'][:6])}")
    if kw["missing_critical_keywords"]:
        print(f"      Missing Critical Keywords ({kw['missing_count']}): {', '.join(kw['missing_critical_keywords'][:6])}")

    # 4. Tailor Resume with Llama
    print(f"\n[4/5] Tailoring Resume using local {model}...")
    tailorer = ResumeTailorer(llm)
    tailored_md = tailorer.generate_tailored_resume(profile, raw_resume, job_data, ats_res)

    # 5. Export Documents
    print(f"\n[5/5] Exporting ATS-Compliant Documents to '{OUTPUT_DIR}'...")
    exporter = DocumentExporter(OUTPUT_DIR)
    md_file = exporter.export_markdown(tailored_md, f"{output_name}.md")
    print(f"      [✓] Markdown: {md_file}")

    try:
        docx_file = exporter.export_docx(tailored_md, f"{output_name}.docx")
        print(f"      [✓] Word DOCX: {docx_file} (ATS Single-Column Format)")
    except Exception as e:
        print(f"      [!] DOCX export skipped ({e}). Run `pip install python-docx` to enable.")

    # Generate Interview Strategy
    print("\n[+] Generating Interview Strategy & Talking Points...")
    prep = tailorer.generate_interview_prep(tailored_md, job_data)
    prep_path = os.path.join(OUTPUT_DIR, f"{output_name}_interview_prep.json")
    with open(prep_path, "w", encoding="utf-8") as f:
        json.dump(prep, f, indent=2)
    print(f"      [✓] Interview Prep saved: {prep_path}")
    print("\n======================================================================")
    print("      SUCCESS! Your tailored resume is ready for submission.")
    print("======================================================================\n")

def main():
    parser = argparse.ArgumentParser(description="Resume Matcher Pro CLI")
    parser.add_argument("--resume", "-r", default=os.path.join(DATA_DIR, "sample_master_resume.md"), help="Path to master resume file")
    parser.add_argument("--job", "-j", default=os.path.join(DATA_DIR, "sample_job_description.txt"), help="Path to job description text file or job URL")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help="Local Llama model name (e.g. llama3.1:8b, llama3.2:3b, llama3.3:70b)")
    parser.add_argument("--host", default=DEFAULT_OLLAMA_HOST, help="Ollama host endpoint")
    parser.add_argument("--output", "-o", default="tailored_resume", help="Base filename for generated resume")
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
        model=args.model,
        host=args.host,
        output_name=args.output
    )

if __name__ == "__main__":
    main()
