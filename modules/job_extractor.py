"""
Job Extractor module.
Handles raw Job Description text and scrapes JDs from URLs (e.g., LinkedIn, Greenhouse, Lever, Indeed, company career pages).
Structures requirements, required skills, and core keywords using local Llama AI.
"""

import re
import json
import logging
from typing import Dict, Any, Optional
import requests

from modules.llm_client import LocalLLMClient

logger = logging.getLogger(__name__)

JOB_SCHEMA = {
    "title": "",
    "company": "",
    "experience_level": "",
    "required_hard_skills": [],
    "nice_to_have_skills": [],
    "tools_and_frameworks": [],
    "core_responsibilities": [],
    "industry_and_domain_keywords": [],
    "education_and_certifications": [],
    "raw_cleaned_text": ""
}

class JobExtractor:
    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.llm = llm_client or LocalLLMClient()

    def scrape_url(self, url: str) -> str:
        """Fetch and extract clean text from a job posting URL."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            raise RuntimeError(f"Failed to fetch job link ({url}): {e}")

        # Try trafilatura if available (state of the art web text extractor)
        try:
            import trafilatura
            extracted = trafilatura.extract(html, include_links=False, include_comments=False)
            if extracted and len(extracted.strip()) > 100:
                return extracted.strip()
        except ImportError:
            pass

        # Try BeautifulSoup
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted tags
            for elem in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "button", "aside"]):
                elem.extract()

            # Attempt to locate common job container elements
            candidates = soup.find_all(attrs={"class": re.compile(r"job|description|posting|req", re.I)})
            if candidates:
                # Pick the longest block
                candidates.sort(key=lambda x: len(x.get_text()), reverse=True)
                text = candidates[0].get_text(separator="\n")
                if len(text.strip()) > 200:
                    return self._clean_text(text)

            text = soup.get_text(separator="\n")
            return self._clean_text(text)
        except ImportError:
            # Fallback regex html tag stripper
            clean = re.sub(r"<[^>]+>", "\n", html)
            clean = re.sub(r"&[a-z]+;", " ", clean)
            return self._clean_text(clean)

    def _clean_text(self, text: str) -> str:
        lines = [line.strip() for line in text.split("\n")]
        # Remove consecutive blank lines
        cleaned_lines = []
        for line in lines:
            if line:
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def parse_job_description(self, jd_text_or_url: str) -> Dict[str, Any]:
        """
        Parses JD text (or scraped URL text) into structured attributes using Llama.
        """
        is_url = bool(re.match(r"^https?://", jd_text_or_url.strip(), re.I))
        if is_url:
            raw_text = self.scrape_url(jd_text_or_url.strip())
        else:
            raw_text = self._clean_text(jd_text_or_url)

        if not raw_text or len(raw_text.strip()) < 50:
            raise ValueError("Job description is too short or empty to analyze.")

        system_prompt = (
            "You are an ATS Keyword Extraction and Job Analysis Engine.\n"
            "Analyze the target job description and extract exact required hard skills, tools, frameworks, "
            "certifications, responsibilities, and industry keywords.\n"
            "Do not invent terms; pull exact keywords used by the employer so ATS parsers match them precisely.\n"
            "Output strictly valid JSON matching the requested schema."
        )

        user_prompt = f"""
Analyze this job description and structure it into the following JSON format:
{json.dumps(JOB_SCHEMA, indent=2)}

JOB DESCRIPTION TEXT:
----------------------------------------
{raw_text[:7000]}
----------------------------------------

Return ONLY valid JSON.
"""
        try:
            parsed = self.llm.generate_json(prompt=user_prompt, system_prompt=system_prompt)
            parsed["raw_cleaned_text"] = raw_text
            # Fill missing keys if any
            for key in JOB_SCHEMA:
                if key not in parsed:
                    parsed[key] = JOB_SCHEMA[key]
            return parsed
        except Exception as e:
            # Fallback extraction if LLM is offline
            return self._heuristic_job_parse(raw_text, error_msg=str(e))

    def _heuristic_job_parse(self, text: str, error_msg: str = "") -> Dict[str, Any]:
        """Fallback rule-based JD extractor."""
        parsed = json.loads(json.dumps(JOB_SCHEMA))
        parsed["raw_cleaned_text"] = text

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            parsed["title"] = lines[0][:100]

        # Extract common tech keywords using regex
        common_tech = [
            "python", "java", "golang", "go", "javascript", "typescript", "c++", "c#",
            "react", "angular", "vue", "node.js", "fastapi", "django", "flask", "spring boot",
            "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "terraform", "linux",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka", "rest api",
            "graphql", "microservices", "git", "machine learning", "pytorch", "llm"
        ]
        text_lower = text.lower()
        found_skills = [skill for skill in common_tech if re.search(rf"\b{re.escape(skill)}\b", text_lower)]
        parsed["required_hard_skills"] = found_skills[:15]
        parsed["tools_and_frameworks"] = found_skills[15:]
        parsed["_fallback_mode"] = True
        parsed["_fallback_notice"] = f"Parsed using regex keywords (LLM note: {error_msg})"
        return parsed
