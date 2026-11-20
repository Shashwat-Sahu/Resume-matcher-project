"""
Resume Parser module.
Reads PDF, DOCX, Markdown, and plain text files.
Converts raw text into a standardized Master Resume schema using local Llama AI.
"""

import os
import json
import re
from typing import Dict, Any, Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
except ImportError:
    docx = None

from modules.llm_client import LocalLLMClient

MASTER_RESUME_SCHEMA = {
    "contact": {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "portfolio": ""
    },
    "summary": "",
    "skills": {
        "languages": [],
        "frameworks_and_libraries": [],
        "cloud_and_devops": [],
        "databases": [],
        "tools_and_platforms": [],
        "methodologies_and_domains": []
    },
    "experience": [
        {
            "company": "",
            "title": "",
            "location": "",
            "dates": "Month YYYY - Month YYYY",
            "bullets": []
        }
    ],
    "projects": [
        {
            "name": "",
            "tech_stack": [],
            "link": "",
            "bullets": []
        }
    ],
    "education": [
        {
            "degree": "",
            "field_of_study": "",
            "institution": "",
            "location": "",
            "graduation_date": "",
            "details": ""
        }
    ],
    "certifications": []
}

class ResumeParser:
    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.llm = llm_client or LocalLLMClient()

    def read_file(self, file_path_or_bytes, filename: str = "") -> str:
        """Extract plain text from PDF, DOCX, TXT, or MD."""
        name = filename or (file_path_or_bytes if isinstance(file_path_or_bytes, str) else "")
        lower_name = name.lower()

        # Handle file paths vs file-like objects (e.g. from Streamlit file_uploader)
        if isinstance(file_path_or_bytes, str):
            if not os.path.exists(file_path_or_bytes):
                raise FileNotFoundError(f"File not found: {file_path_or_bytes}")
            with open(file_path_or_bytes, "rb") as f:
                content_bytes = f.read()
        else:
            if hasattr(file_path_or_bytes, "read"):
                content_bytes = file_path_or_bytes.read()
            else:
                content_bytes = file_path_or_bytes

        if lower_name.endswith(".pdf"):
            return self._extract_pdf(content_bytes)
        elif lower_name.endswith(".docx"):
            return self._extract_docx(content_bytes)
        else:
            # TXT or MD
            try:
                return content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return content_bytes.decode("latin-1", errors="ignore")

    def _extract_pdf(self, content_bytes: bytes) -> str:
        if not PdfReader:
            raise ImportError("pypdf is required to parse PDF files. Run: pip install pypdf")
        import io
        stream = io.BytesIO(content_bytes)
        reader = PdfReader(stream)
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)

    def _extract_docx(self, content_bytes: bytes) -> str:
        if not docx:
            # Fallback if docx not yet installed: attempt xml extraction or raise warning
            raise ImportError("python-docx is required to parse DOCX files. Run: pip install python-docx")
        import io
        stream = io.BytesIO(content_bytes)
        doc = docx.Document(stream)
        text_parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)
        return "\n".join(text_parts)

    def parse_to_master_profile(self, raw_resume_text: str) -> Dict[str, Any]:
        """
        Uses local Llama model to understand the candidate and convert raw resume text into
        a structured Master Profile JSON.
        """
        system_prompt = (
            "You are an expert AI Resume Analyst and Career Architect.\n"
            "Your task is to parse unstructured resume text and convert it into a strictly structured JSON Master Profile.\n"
            "Guidelines:\n"
            "1. Extract all contact information carefully.\n"
            "2. Group technical and soft skills into distinct, accurate categories.\n"
            "3. Standardize dates to 'Month YYYY - Month YYYY' (or 'Month YYYY - Present').\n"
            "4. Preserve all quantifiable metrics, numbers, and impact in experience and project bullets.\n"
            "5. Never invent or hallucinate data; extract faithfully from the provided text.\n"
            "Output strictly valid JSON conforming to the requested schema."
        )

        user_prompt = f"""
Parse the following candidate resume text into this JSON format:
{json.dumps(MASTER_RESUME_SCHEMA, indent=2)}

RESUME TEXT:
----------------------------------------
{raw_resume_text}
----------------------------------------

Return ONLY valid JSON.
"""
        try:
            profile = self.llm.generate_json(prompt=user_prompt, system_prompt=system_prompt)
            # Ensure required top-level keys exist
            for key in MASTER_RESUME_SCHEMA:
                if key not in profile:
                    profile[key] = MASTER_RESUME_SCHEMA[key]
            return profile
        except Exception as e:
            # Fallback to a basic rule-based extraction if LLM is offline
            return self._heuristic_parse(raw_resume_text, error_msg=str(e))

    def _heuristic_parse(self, text: str, error_msg: str = "") -> Dict[str, Any]:
        """Heuristic fallback parser when local LLM is temporarily unreachable."""
        profile = json.loads(json.dumps(MASTER_RESUME_SCHEMA))
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if lines:
            profile["contact"]["name"] = lines[0]

        # Regex for email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        if email_match:
            profile["contact"]["email"] = email_match.group(0)

        # Regex for phone
        phone_match = re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        if phone_match:
            profile["contact"]["phone"] = phone_match.group(0)

        # Regex for linkedin / github
        for line in lines[:10]:
            if "linkedin.com" in line.lower():
                profile["contact"]["linkedin"] = line
            if "github.com" in line.lower():
                profile["contact"]["github"] = line

        profile["summary"] = "\n".join(lines[1:5]) if len(lines) > 5 else "Candidate profile parsed from text."
        profile["_fallback_mode"] = True
        profile["_fallback_notice"] = f"Parsed with heuristic fallback (LLM note: {error_msg})"
        return profile
