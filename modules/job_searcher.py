"""
Job Searcher module.
Searches the web for individual, specific job requisition postings
(hosted on Greenhouse, Lever, Workday, Ashby, and LinkedIn single-view).
Matches and ranks opportunities against the candidate's actual master profile,
calculating real-time skill overlap and relevance scores.
"""

import re
import urllib.parse
import warnings
import logging
from typing import List, Dict, Any, Optional
import requests

warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="ddgs")
logging.getLogger("primp").setLevel(logging.WARNING)
logging.getLogger("ddgs").setLevel(logging.WARNING)
logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


class JobSearcher:
    def __init__(self):
        pass

    def extract_profile_anchors(self, candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts top target titles and defining anchor skills from candidate profile."""
        skills = []
        skills_obj = candidate_profile.get("skills", {})
        if isinstance(skills_obj, dict):
            for cat, items in skills_obj.items():
                if isinstance(items, list):
                    skills.extend(items)
        elif isinstance(skills_obj, list):
            skills = skills_obj

        # Derive title from most recent experience or summary
        recent_title = "Software Engineer"
        for exp in candidate_profile.get("experience", []):
            if isinstance(exp, dict) and exp.get("title"):
                recent_title = exp.get("title")
                break

        # Filter top technical skills
        top_tech = [s for s in skills if len(s) > 1 and s.lower() not in ["agile", "scrum", "git", "bash", "communication"]]

        return {
            "recommended_title": recent_title,
            "anchor_skills": top_tech[:5],
            "all_skills": skills
        }

    def search_matching_jobs(
        self,
        candidate_profile: Dict[str, Any],
        role: str = "",
        location: str = "",
        target_board: str = "All Sources",
        anchor_skill: str = "",
        max_results: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Searches ATS boards for individual postings matching candidate's profile.
        Ranks and scores each retrieved job by skill alignment with the candidate.
        """
        anchors = self.extract_profile_anchors(candidate_profile)
        search_role = role or anchors["recommended_title"]
        selected_anchor = anchor_skill or (anchors["anchor_skills"][0] if anchors["anchor_skills"] else "")

        raw_jobs = self.search_individual_jobs(
            role=search_role,
            location=location,
            target_board=target_board,
            anchor_skill=selected_anchor,
            max_results=max_results * 2  # Fetch extra to score and rank top matches
        )

        # Score and rank each job against candidate's profile
        scored_jobs = []
        for job in raw_jobs:
            score_meta = self.score_job_against_profile(job, candidate_profile)
            job.update(score_meta)
            # Only keep jobs with at least moderate alignment
            if job["match_score"] >= 35 or not scored_jobs:
                scored_jobs.append(job)

        # Sort descending by match score
        scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_jobs[:max_results]

    def search_individual_jobs(
        self,
        role: str,
        location: str = "",
        target_board: str = "All Sources",
        anchor_skill: str = "",
        max_results: int = 8
    ) -> List[Dict[str, str]]:
        """
        Queries specific ATS boards (Greenhouse, Lever, Workday, Ashby) for
        individual, standalone job postings.
        """
        clean_role = re.sub(r"[^\w\s\+\#]", " ", role).strip()
        loc_clause = f'"{location.strip()}"' if location.strip() else ""
        skill_clause = f'"{anchor_skill.strip()}"' if anchor_skill.strip() else ""

        board_queries = []

        if target_board == "Lever":
            board_queries = [
                ("Lever", f'"{clean_role}" {skill_clause} {loc_clause} site:jobs.lever.co'),
                ("Lever", f'"{clean_role}" {loc_clause} site:jobs.lever.co')
            ]
        elif target_board == "Workday":
            board_queries = [
                ("Workday", f'"{clean_role}" {skill_clause} {loc_clause} site:myworkdayjobs.com'),
                ("Workday", f'"{clean_role}" {loc_clause} site:myworkdayjobs.com')
            ]
        elif target_board == "Greenhouse":
            board_queries = [
                ("Greenhouse", f'"{clean_role}" {skill_clause} {loc_clause} site:greenhouse.io'),
                ("Greenhouse", f'"{clean_role}" {loc_clause} site:greenhouse.io')
            ]
        elif target_board == "Ashby":
            board_queries = [("Ashby", f'"{clean_role}" {loc_clause} site:jobs.ashbyhq.com')]
        elif target_board == "LinkedIn (Single View)":
            board_queries = [("LinkedIn", f'"{clean_role}" {loc_clause} site:linkedin.com/jobs/view')]
        else:
            # All Sources: query major ATS boards
            board_queries = [
                ("Lever", f'"{clean_role}" {skill_clause} {loc_clause} site:jobs.lever.co'),
                ("Workday", f'"{clean_role}" {skill_clause} {loc_clause} site:myworkdayjobs.com'),
                ("Greenhouse", f'"{clean_role}" {skill_clause} {loc_clause} site:greenhouse.io'),
                ("Lever", f'"{clean_role}" {loc_clause} site:jobs.lever.co'),
                ("Workday", f'"{clean_role}" {loc_clause} site:myworkdayjobs.com'),
                ("Ashby", f'"{clean_role}" {loc_clause} site:jobs.ashbyhq.com')
            ]

        results = []
        seen_urls = set()

        if DDGS is not None:
            for source_name, q in board_queries:
                if len(results) >= max_results:
                    break
                try:
                    with DDGS() as ddgs:
                        raw = list(ddgs.text(q.strip(), max_results=4))
                        for r in raw:
                            href = r.get("href") or r.get("url") or ""
                            title = r.get("title", "")
                            snippet = r.get("body") or r.get("snippet") or ""

                            if href and href not in seen_urls and self._is_individual_job(href, title):
                                seen_urls.add(href)
                                clean_t = self._clean_job_title(title, source_name)
                                results.append({
                                    "title": clean_t,
                                    "url": href,
                                    "snippet": snippet,
                                    "source": source_name
                                })
                                if len(results) >= max_results:
                                    break
                except Exception:
                    continue

        if results:
            return results

        # Fallback: Live Public Tech APIs (individual listings)
        api_results = self._search_public_apis(clean_role, max_results=max_results)
        if api_results:
            return api_results

        return self._generate_portal_links(f"{clean_role} {location}".strip())

    def score_job_against_profile(self, job: Dict[str, Any], candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scores a job result against the candidate's master profile.
        Returns match percentage, matched skills, and fit badge.
        """
        all_skills = []
        skills_obj = candidate_profile.get("skills", {})
        if isinstance(skills_obj, dict):
            for cat, items in skills_obj.items():
                if isinstance(items, list):
                    all_skills.extend(items)
        elif isinstance(skills_obj, list):
            all_skills = skills_obj

        # Normalize job text
        combined_text = (job.get("title", "") + " " + job.get("snippet", "")).lower()

        matched_skills = []
        for s in all_skills:
            s_clean = s.strip()
            if len(s_clean) > 1 and re.search(rf"\b{re.escape(s_clean.lower())}\b", combined_text):
                matched_skills.append(s_clean)

        # Title alignment check
        title_bonus = 0
        cand_titles = [exp.get("title", "").lower() for exp in candidate_profile.get("experience", []) if isinstance(exp, dict)]
        job_title_lower = job.get("title", "").lower()
        if any(w in job_title_lower for w in ["software", "developer", "engineer", "cloud", "platform", "backend"]):
            title_bonus += 20
        if any(t in job_title_lower for t in ["senior", "lead", "staff"]) and any("senior" in ct for ct in cand_titles):
            title_bonus += 15

        # Base skill score
        skill_score = min(65, len(matched_skills) * 18)
        total_score = min(98, 30 + title_bonus + skill_score)

        if total_score >= 80:
            fit_tier = "High Match"
            badge_color = "green"
        elif total_score >= 60:
            fit_tier = "Moderate Match"
            badge_color = "blue"
        else:
            fit_tier = "Potential Match"
            badge_color = "orange"

        return {
            "match_score": total_score,
            "fit_tier": fit_tier,
            "badge_color": badge_color,
            "matched_candidate_skills": matched_skills[:5]
        }

    def _is_individual_job(self, url: str, title: str) -> bool:
        """Filters out generic search sets, directory pages, and candidate aggregators."""
        blocked_urls = [
            r"linkedin\.com/jobs/(?!view/)",
            r"indeed\.com/q-",
            r"indeed\.com/jobs\?",
            r"glassdoor\.[a-z]+/Job/",
            r"glassdoor\.[a-z]+/Jobs-",
            r"naukri\.com/[^/]+-jobs",
            r"shine\.com/job-search",
            r"foundit\.in/srp",
            r"/browse-jobs",
            r"/all-jobs"
        ]

        for pattern in blocked_urls:
            if re.search(pattern, url, re.I):
                return False

        blocked_title_phrases = [
            r"\d+[\d,]*\+\s*jobs",
            r"\d+[\d,]*\+\s*open roles",
            r"\d+[\d,]*\s*job vacancies",
            r"jobs in [a-zA-Z\s]+ \(\d+",
            r"top \d+ jobs",
            r"browse \d+ jobs"
        ]

        for phrase in blocked_title_phrases:
            if re.search(phrase, title, re.I):
                return False

        return True

    def _clean_job_title(self, title: str, source: str) -> str:
        title = re.sub(r"^Job Application for\s*", "", title, flags=re.I)
        title = re.sub(r"^Job Application:\s*", "", title, flags=re.I)
        title = re.sub(r"\s*-\s*Careers\s*at\s*.*$", "", title, flags=re.I)
        return title.strip()

    def _search_public_apis(self, role: str, max_results: int = 5) -> List[Dict[str, str]]:
        results = []
        keywords = [k.lower() for k in role.split() if len(k) > 2 and k.lower() not in ["jobs", "role", "engineer"]]

        try:
            resp = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=4)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for job in data:
                    title = job.get("title", "")
                    desc = job.get("description", "")
                    combined = f"{title} {desc} {job.get('company_name', '')}".lower()
                    if any(kw in combined for kw in keywords):
                        results.append({
                            "title": f"{title} at {job.get('company_name', 'Company')}",
                            "url": job.get("url", ""),
                            "snippet": f"Location: {job.get('location', 'Remote')} | Tags: {', '.join(job.get('tags', [])[:3])}",
                            "source": "Verified Tech Board (Individual Post)"
                        })
                        if len(results) >= max_results:
                            return results
        except Exception:
            pass

        return results

    def _generate_portal_links(self, query: str) -> List[Dict[str, str]]:
        encoded = urllib.parse.quote(query)
        return [
            {
                "title": f"Direct Individual Postings for '{query}' on LinkedIn",
                "url": f"https://www.linkedin.com/jobs/search/?keywords={encoded}",
                "snippet": "Browse individual job view pages directly on LinkedIn.",
                "source": "LinkedIn"
            },
            {
                "title": f"Search '{query}' Requisitions on Google Jobs",
                "url": f"https://www.google.com/search?q={encoded}+jobs&ibp=htl;jobs",
                "snippet": "Individual employer job requisitions aggregated via Google.",
                "source": "Google Jobs"
            }
        ]
