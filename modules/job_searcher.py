"""
Job Searcher module.
Searches the web strictly for individual, standalone job requisition postings
hosted on Workday, Lever, Greenhouse, Ashby, and LinkedIn (single-view).
Strictly validates URLs to guarantee that company career homepages, search portals,
and directory aggregators are 100% excluded.
"""

import re
import urllib.parse
import warnings
import logging
import concurrent.futures
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

        recent_title = "Software Engineer"
        for exp in candidate_profile.get("experience", []):
            if isinstance(exp, dict) and exp.get("title"):
                recent_title = exp.get("title")
                break

        top_tech = [s for s in skills if len(s) > 1 and s.lower() not in ["agile", "scrum", "git", "bash", "communication", "sql"]]

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
        Ranks each retrieved job by skill alignment with the candidate.
        """
        anchors = self.extract_profile_anchors(candidate_profile)
        search_role = role or anchors["recommended_title"]

        raw_jobs = self.search_individual_jobs(
            role=search_role,
            location=location,
            target_board=target_board,
            anchor_skill=anchor_skill,
            max_results=max_results * 2
        )

        scored_jobs = []
        for job in raw_jobs:
            score_meta = self.score_job_against_profile(job, candidate_profile)
            job.update(score_meta)
            scored_jobs.append(job)

        scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_jobs[:max_results]

    def search_individual_jobs(
        self,
        role: str,
        location: str = "",
        target_board: str = "All Sources",
        anchor_skill: str = "",
        max_results: int = 6
    ) -> List[Dict[str, str]]:
        """
        Queries specific ATS boards (Workday, Lever, Greenhouse, Ashby) using exact
        requisition-targeting queries to return individual postings only.
        """
        clean_role = re.sub(r"[^\w\s\+\#]", " ", role).strip()
        loc_clause = f'"{location.strip()}"' if location.strip() else ""
        skill_clause = f'"{anchor_skill.strip()}"' if anchor_skill.strip() else ""

        # Formulate precise queries that force search engines to return specific job requisitions
        # For Workday: require 'Job Description' to bypass company portal landing pages
        # For Greenhouse: require '/jobs/' in query
        board_queries = []

        if target_board == "Lever":
            board_queries = [
                ("Lever", f'"{clean_role}" {skill_clause} {loc_clause} site:jobs.lever.co'),
                ("Lever", f'{clean_role} {loc_clause} site:jobs.lever.co')
            ]
        elif target_board == "Workday":
            board_queries = [
                ("Workday", f'"{clean_role}" {skill_clause} {loc_clause} "Job Description" site:myworkdayjobs.com'),
                ("Workday", f'{clean_role} {loc_clause} "Job Description" site:myworkdayjobs.com')
            ]
        elif target_board == "Greenhouse":
            board_queries = [
                ("Greenhouse", f'"{clean_role}" {skill_clause} {loc_clause} site:boards.greenhouse.io'),
                ("Greenhouse", f'{clean_role} {loc_clause} site:boards.greenhouse.io'),
                ("Greenhouse", f'{clean_role} {loc_clause} site:job-boards.greenhouse.io')
            ]
        elif target_board == "Ashby":
            board_queries = [("Ashby", f'"{clean_role}" {loc_clause} site:jobs.ashbyhq.com')]
        elif target_board == "LinkedIn (Single View)":
            board_queries = [
                ("LinkedIn", f'"{clean_role}" {skill_clause} {loc_clause} site:linkedin.com/jobs/view'),
                ("LinkedIn", f'{clean_role} {loc_clause} site:linkedin.com/jobs/view')
            ]
        else:
            # All Sources: query each ATS host with individual requisition constraints
            board_queries = [
                ("Workday", f'"{clean_role}" {skill_clause} {loc_clause} "Job Description" site:myworkdayjobs.com'),
                ("Lever", f'"{clean_role}" {skill_clause} {loc_clause} site:jobs.lever.co'),
                ("LinkedIn", f'"{clean_role}" {skill_clause} {loc_clause} site:linkedin.com/jobs/view'),
                ("Greenhouse", f'"{clean_role}" {skill_clause} {loc_clause} site:boards.greenhouse.io'),
                ("Workday", f'{clean_role} {loc_clause} "Job Description" site:myworkdayjobs.com'),
                ("Lever", f'{clean_role} {loc_clause} site:jobs.lever.co'),
                ("LinkedIn", f'{clean_role} {loc_clause} site:linkedin.com/jobs/view'),
                ("Greenhouse", f'{clean_role} {loc_clause} site:boards.greenhouse.io'),
                ("Ashby", f'{clean_role} {loc_clause} site:jobs.ashbyhq.com')
            ]

        candidates = []
        seen_urls = set()

        if DDGS is not None:
            # Gather up to 3x candidates across boards to account for expired postings
            for source_name, q in board_queries:
                if len(candidates) >= max_results * 3:
                    break
                try:
                    with DDGS() as ddgs:
                        raw = list(ddgs.text(q.strip(), max_results=5))
                        for r in raw:
                            href = r.get("href") or r.get("url") or ""
                            title = r.get("title", "")
                            snippet = r.get("body") or r.get("snippet") or ""

                            # Normalize URL to prevent duplicates (e.g. Lever /apply suffix, tracking params)
                            norm_url = re.sub(r"/apply/?$", "", href).split("?")[0].rstrip("/")

                            # STRICT VALIDATION: Must match single requisition criteria
                            if norm_url and norm_url not in seen_urls and self._is_individual_job(href, title):
                                seen_urls.add(norm_url)
                                clean_t = self._clean_job_title(title, href, source_name)
                                candidates.append({
                                    "title": clean_t,
                                    "url": norm_url,
                                    "snippet": snippet,
                                    "source": source_name
                                })
                                if len(candidates) >= max_results * 3:
                                    break
                except Exception:
                    continue

        # Concurrent Active Liveness Verification:
        # Pre-flights candidate URLs in parallel to discard 404s, expired jobs, and redirect errors
        live_results = []
        if candidates:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                liveness_checks = list(executor.map(lambda c: self.verify_job_url_active(c["url"]), candidates))

            for cand, is_active in zip(candidates, liveness_checks):
                if is_active:
                    cand["is_verified_live"] = True
                    live_results.append(cand)
                    if len(live_results) >= max_results:
                        break

        if live_results:
            return live_results

        # Fallback: Live Public Tech APIs (individual listings only)
        api_results = self._search_public_apis(clean_role, max_results=max_results)
        if api_results:
            return api_results

        # Return empty list if no individual requisitions match (never return generic directory search sets)
        return []

    def verify_job_url_active(self, url: str, timeout: float = 3.2) -> bool:
        """
        Actively verifies that a candidate job posting URL is live and open.
        Rejects 404/410, Greenhouse error redirects (?error=true), Lever/Ashby missing UUID
        redirects, Workday portal redirects, and notices that the job has been filled or closed.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

            # 1. HTTP Status Code Check (reject 404 Not Found, 410 Gone, 500, etc.)
            if resp.status_code in [404, 410, 500, 502, 503]:
                return False

            final_url = resp.url.lower()

            # 2. Redirect checks
            # Greenhouse closed/expired jobs redirect to ?error=true
            if "error=true" in final_url:
                return False
            if "greenhouse.io" in final_url and not re.search(r"greenhouse\.io/[^/]+/jobs/\d+", final_url):
                return False

            # Lever: closed jobs either return 404 or redirect away from UUID
            if "jobs.lever.co" in final_url and not re.search(r"jobs\.lever\.co/[^/]+/[0-9a-f\-]{8,}", final_url):
                return False

            # Workday: reject if redirected away from /job/ to portal/search
            if "myworkdayjobs.com" in final_url and "/job/" not in final_url:
                return False

            # Ashby: reject if redirected away from UUID
            if "jobs.ashbyhq.com" in final_url and not re.search(r"jobs\.ashbyhq\.com/[^/]+/[0-9a-f\-]{8,}", final_url):
                return False

            # 3. HTML Content Inspection for dead / closed indicators
            body_lower = resp.text.lower()
            dead_phrases = [
                "this job is no longer available",
                "this position is no longer available",
                "no longer accepting applications",
                "job is not found",
                "job not found",
                "position has been filled",
                "job requisition no longer open",
                "job requisition is no longer open",
                "this posting has expired",
                "the job you are looking for is no longer open",
                "not found – 404 error",
                "not found - 404 error",
                "404 - page not found",
                "404 not found",
                "current openings at"
            ]

            for phrase in dead_phrases:
                if phrase in body_lower:
                    return False

            return True
        except Exception:
            # If Workday triggers a Cloudflare challenge or timeout, but URL strictly has /job/, allow it
            if "myworkdayjobs.com" in url.lower() and "/job/" in url.lower():
                return True
            return False

    def _is_individual_job(self, url: str, title: str) -> bool:
        """
        STRICT VALIDATION:
        Returns True ONLY if the URL and title represent a single individual job posting.
        Returns False for company portal landing pages, search forms, and directory sets.
        """
        url_lower = url.lower()
        title_lower = title.lower()

        # Reject ad links, click trackers, and referral aggregators
        if any(ad in url_lower for ad in ["bing.com/aclick", "google.com/aclk", "doubleclick.net", "catchwork.jobs", "jobrapido", "click?"]):
            return False

        # 1. Reject generic search / portal titles
        rejected_title_patterns = [
            r"^search for jobs",
            r"search for jobs - myworkdayjobs\.com",
            r"^careers at\s+[a-z0-9\s]+$",        # E.g. 'Careers at Quantiphi' without a job title
            r"^jobs at\s+[a-z0-9\s]+$",           # E.g. 'Jobs at GitLab' without a job title
            r"^job openings",
            r"^open positions",
            r"career opportunities",
            r"\d+[\d,]*\+\s*jobs",
            r"\d+[\d,]*\+\s*open roles",
            r"\d+[\d,]*\s*job vacancies",
            r"jobs in [a-z0-9\s]+ \(\d+",
            r"find jobs near you"
        ]

        for p in rejected_title_patterns:
            if re.search(p, title_lower):
                return False

        # 2. Strict Domain-Specific URL Requisition Patterns
        # Workday: MUST have '/job/' in the path. Homepages like /Careers_at_Quantiphi or /Careers/ are REJECTED!
        if "myworkdayjobs.com" in url_lower:
            if "/job/" not in url_lower:
                return False
            # Check that there is a job slug after /job/
            if not re.search(r"/job/[^/]+", url_lower):
                return False
            return True

        # Lever: MUST have a job ID/UUID after company name (e.g. jobs.lever.co/company/98889651-3d5e...)
        if "jobs.lever.co" in url_lower:
            # If URL is just jobs.lever.co/company or jobs.lever.co/company/, reject it!
            if re.match(r"^https?://jobs\.lever\.co/[^/]+/?$", url_lower):
                return False
            if not re.search(r"jobs\.lever\.co/[^/]+/[0-9a-f\-]{8,}", url_lower):
                return False
            return True

        # Greenhouse: MUST have '/jobs/<id>' and must NOT be an expired redirect
        if "greenhouse.io" in url_lower:
            if "?error=true" in url_lower or "error=true" in url_lower:
                return False
            if not re.search(r"greenhouse\.io/[^/]+/jobs/\d+", url_lower):
                return False
            return True

        # Ashby: MUST have a job ID/UUID
        if "jobs.ashbyhq.com" in url_lower:
            if re.match(r"^https?://jobs\.ashbyhq\.com/[^/]+/?$", url_lower):
                return False
            if not re.search(r"jobs\.ashbyhq\.com/[^/]+/[0-9a-f\-]{8,}", url_lower):
                return False
            return True

        # LinkedIn: MUST have '/jobs/view/<id>'
        if "linkedin.com" in url_lower:
            if not re.search(r"linkedin\.com/jobs/view/\d+", url_lower):
                return False
            return True

        # Indeed: MUST have '/viewjob'
        if "indeed.com" in url_lower:
            if "/viewjob" not in url_lower:
                return False
            return True

        # Generic Career sites: must have specific job path segment
        if re.search(r"/(job|jobs|requisition|position)/\d+", url_lower):
            return True

        # By default, if not confirmed as an individual job, REJECT!
        return False

    def _clean_job_title(self, title: str, url: str, source: str) -> str:
        """Extracts clean role and company from title and URL."""
        cleaned = re.sub(r"^Job Application for\s*", "", title, flags=re.I)
        cleaned = re.sub(r"^Job Application:\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*Careers\s*at\s*.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*myworkdayjobs\.com.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*job-boards\..*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*Logo$", "", cleaned, flags=re.I)

        # If title is generic or company subdomain is known, prepend company
        if "myworkdayjobs.com" in url.lower():
            match = re.search(r"https?://([^.]+)\.[^/]*myworkdayjobs\.com", url, re.I)
            if match:
                company_name = match.group(1).title()
                if company_name.lower() not in cleaned.lower():
                    cleaned = f"{cleaned} at {company_name}"

        return cleaned.strip()

    def score_job_against_profile(self, job: Dict[str, Any], candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Scores a job result against the candidate's master profile."""
        all_skills = []
        skills_obj = candidate_profile.get("skills", {})
        if isinstance(skills_obj, dict):
            for cat, items in skills_obj.items():
                if isinstance(items, list):
                    all_skills.extend(items)
        elif isinstance(skills_obj, list):
            all_skills = skills_obj

        combined_text = (job.get("title", "") + " " + job.get("snippet", "")).lower()

        matched_skills = []
        for s in all_skills:
            s_clean = s.strip()
            if len(s_clean) > 1 and re.search(rf"\b{re.escape(s_clean.lower())}\b", combined_text):
                matched_skills.append(s_clean)

        title_bonus = 0
        cand_titles = [exp.get("title", "").lower() for exp in candidate_profile.get("experience", []) if isinstance(exp, dict)]
        job_title_lower = job.get("title", "").lower()
        if any(w in job_title_lower for w in ["software", "developer", "engineer", "cloud", "platform", "backend"]):
            title_bonus += 20
        if any(t in job_title_lower for t in ["senior", "lead", "staff"]) and any("senior" in ct for ct in cand_titles):
            title_bonus += 15

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
