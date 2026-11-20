"""
Application Tracker Module.
Maintains a persistent record of all tailored resumes generated:
- Target Job Title & Company
- Target Job URL (or source)
- Generation timestamp
- ATS score and keyword gap metrics
- Generated file artifacts (PDF, DOCX, Markdown, Interview Prep JSON)
"""

import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

class ApplicationTracker:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.history_file = os.path.join(output_dir, "applications_history.json")
        os.makedirs(output_dir, exist_ok=True)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.history_file):
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def load_history(self) -> List[Dict[str, Any]]:
        """Loads all recorded tailored resume history."""
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def record_application(
        self,
        candidate_name: str,
        job_title: str,
        company: str,
        job_url: str,
        ats_score: int,
        breakdown: Dict[str, Any],
        pdf_path: str,
        docx_path: str,
        md_path: str,
        interview_prep_path: Optional[str] = None,
        top_skills: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Records a newly generated tailored resume application into history.
        """
        history = self.load_history()
        now = datetime.now()

        # Sanitize name and company for slugs
        clean_company = re.sub(r"[^\w\-]", "_", company or "Company").strip("_")
        clean_title = re.sub(r"[^\w\-]", "_", job_title or "Role").strip("_")
        entry_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{clean_company}_{clean_title}"

        record = {
            "id": entry_id,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "candidate_name": candidate_name or "Candidate",
            "job_title": job_title or "Target Role",
            "company": company or "Target Company",
            "job_url": job_url or "Direct Text Input",
            "ats_score": ats_score,
            "breakdown": breakdown or {},
            "top_skills": top_skills or [],
            "files": {
                "pdf": pdf_path,
                "docx": docx_path,
                "markdown": md_path,
                "interview_prep": interview_prep_path
            }
        }

        # Prepend to show latest first
        history.insert(0, record)

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        return record

    def delete_record(self, record_id: str) -> bool:
        """Removes a record from history."""
        history = self.load_history()
        filtered = [r for r in history if r.get("id") != record_id]
        if len(filtered) != len(history):
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2)
            return True
        return False
