# 🎯 Resume Matcher Pro (Local Llama AI + ATS Optimizer)

An AI-powered career tool that connects to **100% local Llama models** to parse your master resume, analyze target job descriptions (via text, live URL scraping, or automated job search), evaluate **ATS compatibility scores**, and generate tailored resumes and interview preparation strategies that pass recruiter filters.

---

## 🌟 Key Features

1. **🔒 100% Local & Private AI:**
   - Powered by Meta's Llama family via **Ollama**.
   - Zero cloud data leakage. Your career data, salary details, and resume remain on your local machine.

2. **📄 Master Resume Intelligence:**
   - Accepts PDF, Word DOCX, Markdown, and TXT master resumes.
   - Parses your complete work history, skills taxonomy, and quantified achievements into a structured profile.

3. **💼 Three Flexible Job Intake Modes:**
   - **Mode A (Direct Text):** Paste any job description directly.
   - **Mode B (URL Scraper):** Provide any job posting link (Greenhouse, Lever, LinkedIn, Workday, or corporate career sites). The scraper strips navigation, ads, and footers to extract requirements cleanly.
   - **Mode C (Automated Job Search):** Searches live openings across ATS boards matching your target role and skills with 1-click selection.

4. **📊 Empirical ATS Scoring Engine (0–100%):**
   - **Keyword Match Score (45% weight):** Exact & semantic taxonomy match against target JD hard skills and tools.
   - **Quantification & Impact Score (25% weight):** Audits accomplishment bullets using Google's XYZ formula (`Accomplished [X] measured by [Y] doing [Z]`).
   - **Structural Safety Score (30% weight):** Enforces single-column rules, standard section headings, and safe date formats for Workday and Greenhouse.
   - **Keyword Gap Analysis:** Highlights exact matches vs. high-priority missing keywords.

5. **✨ AI Resume Tailoring:**
   - Rewrites and reframes your authentic experience specifically for the target role without hallucinating or fabricating facts.
   - Injects required keywords into the summary, skills taxonomy, and contextual accomplishment bullets.

6. **📁 100% ATS-Compliant File Export:**
   - **DOCX (.docx):** The single safest format for Workday, Greenhouse, and Lever. Built with single-column hierarchy, standard margins, and native bullet styles (no text boxes or headers/footers).
   - **Markdown (.md):** Clean text structure for developers and version control.
   - **Plain Text (.txt):** Instant copy-paste for standard application text areas.

7. **🎙️ Strategic Interview Preparation:**
   - Generates a customized 60-second elevator pitch ("Tell me about yourself").
   - Predicts top technical questions and recommended talking points.
   - Formulates behavioral STAR answers.
   - Identifies candidate-job gaps with bridging strategies.
   - Provides smart questions to ask the interviewer.

---

## 🤖 Recommended Llama Models

| Model | Size / VRAM | Best For | Recommended Command |
|---|---|---|---|
| **Llama 3.1 (8B Instruct)** ⭐ *(Top Recommendation)* | ~4.7 GB / 8 GB VRAM or 16 GB RAM | Best balance of intelligence, keyword extraction precision, and speed. | `ollama run llama3.1:8b` |
| **Llama 3.2 (3B Instruct)** | ~2.0 GB / 4 GB VRAM or 8 GB RAM | Ultra-fast execution, perfect for laptops or quick iterations. | `ollama run llama3.2:3b` |
| **Llama 3.3 (70B Instruct)** | ~40 GB / 24+ GB VRAM or 64 GB RAM | Frontier-class reasoning, executive-level nuance, complex rewrites. | `ollama run llama3.3:70b` |

---

## 📋 ATS Optimization Tactics (Based on Empirical Industry Testing)

Modern platforms like **Workday, Greenhouse, and Lever** do not use arbitrary "robot rejection scores". They parse your document into structured database fields and rank you for human recruiters. If your formatting breaks the parser, your ranking drops to zero.

### 1. The Single-Column Rule
- **Never use 2-column templates, tables, or sidebars.**
- Parsers read horizontally line-by-line, combining your sidebar skills into job bullets and turning experience into unreadable gibberish.

### 2. Contact Info in Main Body
- **Never place phone, email, or LinkedIn in document headers or footers.**
- Workday's parser completely strips headers and footers during plain-text extraction. Keep contact info in the first paragraph of the main page body.

### 3. Exact Standard Section Headings
- Use recognized names: `Professional Summary`, `Work Experience`, `Technical Skills`, `Key Projects`, `Education`, `Certifications`.
- Avoid artistic names like "My Journey" or "Core Competencies".

### 4. Standard Date Formats
- Format strictly as `Month YYYY – Month YYYY` (e.g. `July 2021 – Present` or `06/2019 – 11/2022`).
- Ambiguous dates or season names (e.g., "Summer 2021") prevent ATS tenure calculations.

### 5. Google XYZ Formula for Recruiter Engagement
- Human recruiters scan resumes for **6 to 8 seconds**.
- Upgrade bullets from passive duty lists to quantified accomplishments:
  > **Accomplished [X] as measured by [Y] by doing [Z]**
  - *Weak:* "Responsible for building backend APIs in Python."
  - *Strong:* "Architected and deployed 14+ cloud-native microservices using Python (FastAPI) and PostgreSQL on AWS, reducing p99 API response latency by 77% and supporting 2.4M daily active users."

---

## 🚀 Quick Start Guide

### Step 1: Ensure Ollama is Running
If you don't have Ollama, download it from [ollama.com](https://ollama.com).

Open PowerShell and pull your preferred Llama model:
```bash
ollama run llama3.1:8b
```

### Step 2: Install Python Dependencies
Double-click `install.bat` or run:
```bash
pip install -r requirements.txt
```

### Step 3: Launch the Application

#### Option A: Interactive Web UI (Recommended)
Double-click `run.bat` or run:
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

#### Option B: Command Line (CLI)
To run an automated test using the included sample master resume and sample job:
```bash
python main.py
```
To run on your own files:
```bash
python main.py --resume path/to/your_resume.docx --job path/to/job_description.txt --model llama3.1:8b
```
To pass a live job URL directly:
```bash
python main.py --resume path/to/your_resume.pdf --job "https://boards.greenhouse.io/company/jobs/12345"
```

---

## 📂 Project Structure

```
D:\AI projects\resume matcher project\
│
├── app.py                      # Interactive Streamlit Web Application
├── main.py                     # CLI Automation Script
├── config.py                   # Model configurations and system settings
├── requirements.txt            # Python dependencies
├── run.bat                     # 1-Click launcher for Windows
├── install.bat                 # 1-Click installer for dependencies
├── README.md                   # Complete documentation & ATS guide
│
├── modules/
│   ├── __init__.py
│   ├── llm_client.py           # Local Ollama / OpenAI-compatible connector
│   ├── resume_parser.py        # PDF, DOCX, TXT, MD parser and schema extractor
│   ├── job_extractor.py        # JD text cleaner and URL web scraper
│   ├── ats_optimizer.py        # ATS scoring engine and keyword gap analysis
│   ├── resume_tailorer.py      # Llama prompting and resume tailoring logic
│   ├── document_exporter.py    # ATS-safe DOCX, Markdown, and TXT exporter
│   └── job_searcher.py         # Live web search for ATS board openings
│
├── data/
│   ├── sample_master_resume.md # Ready-to-use sample master resume
│   └── sample_job_description.txt # Sample high-tier cloud engineer JD
│
├── templates/
│   └── ats_style_guide.md      # Detailed ATS and Recruiter Tactics Guide
│
└── output/                     # Generated tailored resumes (.docx, .md, .txt)
```

---

## 🛡️ License & Privacy
This application runs entirely on your local machine with local open-weights AI models. No data is sent to external cloud APIs or third parties.
