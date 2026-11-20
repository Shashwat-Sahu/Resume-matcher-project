"""
ATS Optimizer and Scoring Engine.
Applies empirical ATS heuristics (Workday, Greenhouse, Lever, Taleo):
1. Hard/Soft keyword match ratio & keyword gap analysis
2. Google XYZ formula / quantification check (metrics, %, $, scale)
3. Structural parsing safety (single-column compliance, standard headings, date formats)
4. Overall ATS Compatibility Score (0 - 100)
5. Before vs After comparison engine for tailored resumes
"""

import re
from typing import Dict, Any, List, Set, Tuple

STANDARD_ATS_SECTIONS = [
    "summary", "work experience", "experience", "skills", "technical skills",
    "education", "projects", "certifications"
]

class ATSOptimizer:
    def __init__(self):
        pass

    def calculate_ats_score(self, resume_data: Dict[str, Any], job_data: Dict[str, Any], raw_resume_text: str) -> Dict[str, Any]:
        """
        Computes detailed ATS breakdown score and gap analysis.
        Works seamlessly on both structured master profiles and raw markdown tailored resumes.
        """
        # 1. Keyword Gap Analysis
        kw_analysis = self.analyze_keywords(resume_data, job_data, raw_resume_text)

        # 2. Metric / Quantification Density (Google XYZ formula)
        metric_analysis = self.analyze_quantification(resume_data, raw_resume_text)

        # 3. Structural & Formatting Safety Check
        format_analysis = self.analyze_format_safety(raw_resume_text, resume_data)

        # 4. Overall Weighted ATS Score Calculation
        # Weights:
        # Keyword Match: 50%
        # Quantification / Impact: 25%
        # Formatting & ATS Safety: 25%
        kw_score = kw_analysis["match_percentage"]
        impact_score = metric_analysis["quantification_score"]
        safety_score = format_analysis["safety_score"]

        composite_score = round((kw_score * 0.50) + (impact_score * 0.25) + (safety_score * 0.25))
        composite_score = max(0, min(100, composite_score))

        # Overall rating badge
        if composite_score >= 85:
            rating = "Excellent (Top 5% ATS Match - High Interview Probability)"
            badge_color = "green"
        elif composite_score >= 70:
            rating = "Good (Competitive Match - Ready with Minor Keyword Tweaks)"
            badge_color = "blue"
        elif composite_score >= 50:
            rating = "Moderate (At Risk of Recruiter Filter Drop - Optimization Needed)"
            badge_color = "orange"
        else:
            rating = "Low (High Risk of ATS Disqualification - Critical Gaps)"
            badge_color = "red"

        return {
            "overall_score": composite_score,
            "rating": rating,
            "badge_color": badge_color,
            "breakdown": {
                "keyword_match_score": kw_score,
                "quantification_impact_score": impact_score,
                "formatting_safety_score": safety_score
            },
            "keyword_analysis": kw_analysis,
            "quantification_analysis": metric_analysis,
            "formatting_analysis": format_analysis,
            "actionable_tips": self._generate_actionable_tips(kw_analysis, metric_analysis, format_analysis)
        }

    def compare_ats_scores(self, before_res: Dict[str, Any], after_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compares initial Master Resume ATS evaluation with the Tailored Resume evaluation.
        Computes score deltas, newly integrated keywords, and remaining gaps.
        """
        score_before = before_res.get("overall_score", 0)
        score_after = after_res.get("overall_score", 0)
        delta_score = score_after - score_before

        kw_before = set(before_res.get("keyword_analysis", {}).get("matched_keywords", []))
        kw_after = set(after_res.get("keyword_analysis", {}).get("matched_keywords", []))

        # Keywords newly incorporated into the tailored resume
        newly_matched = sorted(list(kw_after - kw_before), key=lambda x: x.lower())
        remaining_missing = after_res.get("keyword_analysis", {}).get("missing_critical_keywords", [])

        kw_pct_before = before_res.get("breakdown", {}).get("keyword_match_score", 0)
        kw_pct_after = after_res.get("breakdown", {}).get("keyword_match_score", 0)
        delta_kw = kw_pct_after - kw_pct_before

        impact_before = before_res.get("breakdown", {}).get("quantification_impact_score", 0)
        impact_after = after_res.get("breakdown", {}).get("quantification_impact_score", 0)
        delta_impact = impact_after - impact_before

        return {
            "score_before": score_before,
            "score_after": score_after,
            "score_delta": delta_score,
            "rating_before": before_res.get("rating", "N/A"),
            "rating_after": after_res.get("rating", "N/A"),
            "keyword_match_before": kw_pct_before,
            "keyword_match_after": kw_pct_after,
            "keyword_match_delta": delta_kw,
            "impact_before": impact_before,
            "impact_after": impact_after,
            "impact_delta": delta_impact,
            "newly_matched_keywords": newly_matched,
            "newly_matched_count": len(newly_matched),
            "remaining_missing": remaining_missing,
            "remaining_missing_count": len(remaining_missing)
        }

    def analyze_keywords(self, resume_data: Dict[str, Any], job_data: Dict[str, Any], raw_resume_text: str) -> Dict[str, Any]:
        """Identifies matched, missing, and partial keywords between resume and job description."""
        target_keywords = set()
        for k in ["required_hard_skills", "tools_and_frameworks", "industry_and_domain_keywords", "nice_to_have_skills"]:
            for item in job_data.get(k, []):
                cleaned = str(item).strip()
                if cleaned and len(cleaned) > 1:
                    target_keywords.add(cleaned)

        resume_text_lower = raw_resume_text.lower()

        candidate_skills = set()
        skills_obj = resume_data.get("skills", {})
        if isinstance(skills_obj, dict):
            for cat, items in skills_obj.items():
                if isinstance(items, list):
                    for it in items:
                        candidate_skills.add(str(it).lower().strip())
        elif isinstance(skills_obj, list):
            for it in skills_obj:
                candidate_skills.add(str(it).lower().strip())

        matched_exact = []
        missing = []

        for kw in target_keywords:
            kw_clean = kw.lower()
            pattern = rf"\b{re.escape(kw_clean)}\b"
            if re.search(pattern, resume_text_lower) or kw_clean in candidate_skills:
                matched_exact.append(kw)
            else:
                missing.append(kw)

        total_kw = len(target_keywords)
        matched_count = len(matched_exact)
        match_pct = round((matched_count / total_kw * 100)) if total_kw > 0 else 85

        return {
            "total_job_keywords": total_kw,
            "matched_count": matched_count,
            "missing_count": len(missing),
            "match_percentage": min(100, match_pct),
            "matched_keywords": sorted(matched_exact, key=lambda x: x.lower()),
            "missing_critical_keywords": sorted(missing, key=lambda x: x.lower())
        }

    def analyze_quantification(self, resume_data: Dict[str, Any], raw_resume_text: str) -> Dict[str, Any]:
        """
        Assesses bullets for Google XYZ formula / quantification (numbers, %, $, multipliers, latency).
        Only measures accomplishment bullets in Experience & Projects (ignoring skill category lines).
        """
        bullets = []

        # 1. From structured data if present
        for exp in resume_data.get("experience", []):
            if isinstance(exp, dict):
                for b in exp.get("bullets", []):
                    if isinstance(b, str) and b.strip():
                        bullets.append(b.strip())

        for proj in resume_data.get("projects", []):
            if isinstance(proj, dict):
                for b in proj.get("bullets", []):
                    if isinstance(b, str) and b.strip():
                        bullets.append(b.strip())

        # 2. From raw text if structured data was empty
        if not bullets:
            in_experience_or_projects = False
            for line in raw_resume_text.split("\n"):
                sline = line.strip()
                if sline.startswith("## "):
                    header_lower = sline.lower()
                    if any(h in header_lower for h in ["experience", "project", "work history"]):
                        in_experience_or_projects = True
                    elif any(h in header_lower for h in ["skills", "education", "certifications"]):
                        in_experience_or_projects = False

                if in_experience_or_projects:
                    # Look for bullet lines, but skip bold skill category lines like "- **Languages:**"
                    if sline.startswith(("- ", "• ", "* ", "– ")) and len(sline) > 15:
                        content = sline.lstrip("-•*– ").strip()
                        if not re.match(r"^\*\*[A-Za-z\s]+:\*\*", content):
                            bullets.append(content)

        # Comprehensive regex for metric markers: %, $, multipliers, numbers with units, latencies, scales
        metric_pattern = re.compile(
            r"(\b\d+(\.\d+)?%\b|\$\d+[\d,]*(\.\d+)?[kmb]?|\b\d+x\b|\b\d+\s*\+\b|\b\d+[\d,]*\s*(ms|users|clients|customers|requests|queries|downloads|events|req/s|rps|million|billion|k\b|engineers|services))",
            re.I
        )

        quantified_bullets = []
        unquantified_bullets = []

        for b in bullets:
            if metric_pattern.search(b):
                quantified_bullets.append(b)
            else:
                unquantified_bullets.append(b)

        total = len(bullets)
        quantified_count = len(quantified_bullets)
        ratio = (quantified_count / total) if total > 0 else 0.75
        score = round(min(100, ratio * 125))

        return {
            "total_bullets_analyzed": total,
            "quantified_bullets_count": quantified_count,
            "quantification_ratio": round(ratio * 100, 1),
            "quantification_score": score,
            "sample_quantified": quantified_bullets[:3],
            "needs_metric_samples": unquantified_bullets[:3]
        }

    def analyze_format_safety(self, raw_resume_text: str, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies ATS formatting compliance:
        - Clean standard headings (Summary, Experience, Education, Skills)
        - Standard date formatting Month YYYY - Month YYYY
        - Contact info availability in body
        """
        deductions = 0
        issues = []
        checks_passed = []

        # 1. Contact check
        if not re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_resume_text):
            deductions += 20
            issues.append("Missing email in body text.")
        else:
            checks_passed.append("Email detected in body text.")

        if not re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", raw_resume_text):
            deductions += 10
            issues.append("Phone number not found in main body.")
        else:
            checks_passed.append("Phone number detected.")

        # 2. Standard section headers check
        text_lower = raw_resume_text.lower()
        found_sections = [sec for sec in STANDARD_ATS_SECTIONS if sec in text_lower]
        if len(found_sections) < 3:
            deductions += 15
            issues.append("Fewer standard section headings detected.")
        else:
            checks_passed.append(f"Standard section headings verified ({len(found_sections)} found).")

        # 3. Standard date checks
        date_pattern = re.compile(
            r"\b(Jan(uary)?|Feb(ruary)?|Mar(ch)?|Apr(il)?|May|Jun(e)?|Jul(y)?|Aug(ust)?|Sep(tember)?|Oct(ober)?|Nov(ember)?|Dec(ember)?|\d{1,2}/\d{4})\s*(\d{4})?\s*[-–—to]+\s*(Present|Current|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2}/\d{4})\s*\d{4})",
            re.I
        )
        if not date_pattern.search(raw_resume_text):
            deductions += 10
            issues.append("Dates should follow 'Month YYYY – Month YYYY' format.")
        else:
            checks_passed.append("Standard chronological date patterns detected.")

        safety_score = max(20, 100 - deductions)

        return {
            "safety_score": safety_score,
            "issues": issues,
            "checks_passed": checks_passed
        }

    def _generate_actionable_tips(self, kw: Dict[str, Any], metric: Dict[str, Any], fmt: Dict[str, Any]) -> List[str]:
        tips = []

        if kw["missing_critical_keywords"]:
            top_missing = ", ".join(f"'{k}'" for k in kw["missing_critical_keywords"][:5])
            tips.append(
                f"**Integrate High-Priority Missing Keywords:** Your resume is missing {top_missing}. "
                "Embed these directly into your Skills section and contextual experience bullets."
            )

        if metric["quantification_ratio"] < 60:
            tips.append(
                f"**Upgrade Bullets with Google XYZ Formula:** Only {metric['quantification_ratio']}% of your bullets contain numbers or metrics. "
                "Recruiters scan for quantifiable results: rewrite bullets as 'Accomplished [X], as measured by [Y], by doing [Z]'."
            )

        for issue in fmt.get("issues", []):
            tips.append(f"**ATS Parser Fix:** {issue}")

        tips.append(
            "**Recruiter 6-Second Hook:** Position your most relevant technical accomplishments and domain keywords "
            "in the top third of Page 1 (Professional Summary & first 2 bullets of your latest role)."
        )

        return tips
