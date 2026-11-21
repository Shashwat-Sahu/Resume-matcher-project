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
    MONTHS = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    def __init__(self):
        pass

    def calculate_candidate_seniority(self, candidate_profile: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
        """
        Accurately calculates candidate's total years of experience and seniority tier (0-4)
        from experience date ranges, job titles, and resume summary.
        """
        total_months = 0
        exps = candidate_profile.get("experience", [])
        for exp in exps:
            if not isinstance(exp, dict):
                continue
            dates = exp.get("dates", "")
            if not dates:
                continue
            parts = re.split(r"\s*(?:[-–—\u2013\u2014]|\bto\b)\s*", dates, flags=re.I)
            if len(parts) >= 2:
                sy, sm = self._parse_date_string(parts[0])
                ey, em = self._parse_date_string(parts[1])
                if sy and ey:
                    diff = (ey - sy) * 12 + (em - sm)
                    if diff > 0:
                        total_months += diff

        years = round(total_months / 12, 1)
        if years == 0:
            m = re.search(r"(\d+)\+?\s*years(?:\s+of)?\s+experience", raw_text or candidate_profile.get("summary", ""), re.I)
            if m:
                years = float(m.group(1))
            else:
                years = max(1.5, len(exps) * 1.5)

        titles = [e.get("title", "").lower() for e in exps if isinstance(e, dict)]
        titles_str = " ".join(titles)

        # 1. Staff / Principal / Architect / Director
        if any(w in titles_str for w in ["staff", "principal", "architect", "director", "vp"]) or years >= 8:
            tier, label = 4, "Staff / Lead (8+ Yrs)"
        # 2. Senior / Tech Lead / SDE 3
        elif any(w in titles_str for w in ["senior", "sr.", "lead", "sde 3", "sde iii", "sde-3"]) or years >= 5:
            tier, label = 3, "Senior (5-8 Yrs)"
        # 3. Explicit SDE 2 / Mid-Level
        elif any(w in titles_str for w in [
            "sde 2", "sde ii", "sde-2", "sde-ii",
            "software engineer 2", "software engineer ii",
            "software development engineer 2", "software development engineer ii",
            "developer 2", "developer ii", "engineer 2", "engineer ii"
        ]) or (years >= 2 and years < 5):
            tier, label = 2, "Mid-Level / SDE 2 (2-5 Yrs)"
        # 4. Junior / Early Career / SDE 1
        elif any(w in titles_str for w in ["junior", "associate", "trainee", "graduate", "sde 1", "sde i", "sde-1"]) or years <= 2:
            tier, label = 1, "Early Career / Junior (0-2 Yrs)"
        else:
            tier, label = 2, "Mid-Level / SDE 2 (2-5 Yrs)"

        return {
            "years": years,
            "tier": tier,
            "label": label
        }

    def _parse_date_string(self, d_str: str):
        d_str = d_str.strip().lower()
        if any(w in d_str for w in ["present", "current", "now"]):
            return 2026, 11
        m = re.search(r"([a-z]{3,9})[\s,]+(20\d\d|19\d\d)", d_str)
        if m:
            month = self.MONTHS.get(m.group(1)[:3], 6)
            return int(m.group(2)), month
        m_yr = re.search(r"(20\d\d|19\d\d)", d_str)
        if m_yr:
            return int(m_yr.group(1)), 6
        return None, None

    def detect_job_seniority(self, title: str, snippet: str = "") -> Dict[str, Any]:
        """
        Classifies the target job's required seniority tier (0-4) based on
        title prefixes, suffixes, and requirements phrases in the text.
        """
        t_lower = title.lower()
        text = (t_lower + " " + snippet).lower()

        # Tier 4: Staff / Principal / Architect / Executive
        if any(w in t_lower for w in ["staff", "principal", "architect", "lead architect", "director", "vp", "head of"]) or any(w in text for w in ["8+ years", "10+ years", "staff software engineer", "staff engineer"]):
            return {"tier": 4, "label": "Staff / Lead (8+ Yrs)"}

        # Tier 3: Senior / Tech Lead
        if any(w in t_lower for w in ["senior", "sr.", "sr ", "iii", "sde 3", "sde iii", "tech lead", "team lead"]) or any(w in text for w in ["5+ years", "6+ years", "7+ years", "senior engineer"]):
            return {"tier": 3, "label": "Senior (5-8 Yrs)"}

        # Tier 0: Intern
        if any(w in t_lower for w in ["intern", "co-op", "internship", "trainee"]):
            return {"tier": 0, "label": "Intern (0 Yrs)"}

        # Tier 1: Early Career / Junior / Associate
        if any(w in t_lower for w in ["junior", "entry", "associate", "graduate", "sde 1", "sde i"]) or any(w in text for w in ["0-1 year", "0-2 years", "entry level", "freshers"]):
            return {"tier": 1, "label": "Early Career / Junior (0-2 Yrs)"}

        # Tier 2: Mid-Level (default for plain Software Engineer / Developer)
        return {"tier": 2, "label": "Mid-Level (2-5 Yrs)"}

    def extract_profile_anchors(self, candidate_profile: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
        """Extracts top target titles, defining anchor skills, and seniority tier from candidate profile."""
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
        seniority = self.calculate_candidate_seniority(candidate_profile, raw_text)

        return {
            "recommended_title": recent_title,
            "anchor_skills": top_tech[:5],
            "all_skills": skills,
            "seniority": seniority
        }

    def search_matching_jobs(
        self,
        candidate_profile: Dict[str, Any],
        role: str = "",
        location: str = "",
        target_board: str = "All Sources",
        anchor_skill: str = "",
        target_seniority: str = "Auto-Match Resume",
        max_results: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Searches ATS boards for individual postings matching candidate's profile.
        Strictly filters out jobs that have significant seniority mismatches (e.g. Staff
        level roles for Junior/Mid-level candidates).
        """
        anchors = self.extract_profile_anchors(candidate_profile)
        search_role = role or anchors["recommended_title"]

        # Resolve target seniority tier
        cand_tier = anchors["seniority"]["tier"]
        if "early career" in target_seniority.lower() or "junior" in target_seniority.lower():
            filter_tier = 1
        elif "mid-level" in target_seniority.lower():
            filter_tier = 2
        elif "senior" in target_seniority.lower():
            filter_tier = 3
        elif "staff" in target_seniority.lower() or "principal" in target_seniority.lower():
            filter_tier = 4
        elif "all levels" in target_seniority.lower():
            filter_tier = -1
        else:
            filter_tier = cand_tier

        raw_jobs = self.search_individual_jobs(
            role=search_role,
            location=location,
            target_board=target_board,
            anchor_skill=anchor_skill,
            max_results=max_results * 4
        )

        scored_jobs = []
        for job in raw_jobs:
            job_sen = self.detect_job_seniority(job.get("title", ""), job.get("snippet", ""))
            job_title_lower = job.get("title", "").lower()

            # 1. HARD BLOCK ON INTERNSHIPS:
            # If candidate is a working professional / experienced engineer (Tier >= 1, e.g. SDE 1, SDE 2, Senior),
            # NEVER suggest an internship!
            if filter_tier >= 1 and (
                job_sen["tier"] == 0 or
                any(w in job_title_lower for w in ["intern", "internship", "co-op", "stipend", "fellowship"])
            ):
                continue

            # 2. HARD BLOCK ON STAFF/PRINCIPAL FOR JUNIOR & MID-LEVEL:
            # If candidate is SDE 1 or SDE 2 (Tier <= 2), NEVER suggest Staff / Principal / Architect / Lead!
            if filter_tier <= 2 and (
                job_sen["tier"] >= 4 or
                any(w in job_title_lower for w in ["staff", "principal", "architect", "director", "vp", "head of"])
            ):
                continue

            # 3. SENIORITY GUARD:
            # Junior candidates (Tier 1) should not be suggested Senior (Tier 3) or Staff (Tier 4)
            if filter_tier == 1 and job_sen["tier"] >= 3:
                continue

            # SDE 2 / Mid-level candidates (Tier 2) should not be suggested Staff (Tier 4) or Intern (Tier 0)
            if filter_tier == 2 and (job_sen["tier"] >= 4 or job_sen["tier"] == 0):
                continue

            score_meta = self.score_job_against_profile(job, candidate_profile, filter_tier)
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
        max_results: int = 10
    ) -> List[Dict[str, str]]:
        """
        Queries specific ATS boards (Workday, Lever, Greenhouse, Ashby, SmartRecruiters, LinkedIn)
        using exact requisition-targeting queries to return individual postings only.
        """
        clean_role = re.sub(r"[^\w\s\+\#]", " ", role).strip()
        loc_clause = f'"{location.strip()}"' if location.strip() else ""
        skill_clause = f'"{anchor_skill.strip()}"' if anchor_skill.strip() else ""

        # Formulate precise queries that force search engines to return specific job requisitions
        board_queries = []

        tb_lower = target_board.lower()
        if "top mnc" in tb_lower:
            board_queries = [
                ("Amazon", f'{clean_role} {loc_clause} site:amazon.jobs/en/jobs'),
                ("Microsoft", f'{clean_role} {loc_clause} site:jobs.careers.microsoft.com'),
                ("Google", f'{clean_role} {loc_clause} "careers.google.com/jobs/results"'),
                ("Apple", f'{clean_role} {loc_clause} site:jobs.apple.com details'),
                ("Meta", f'{clean_role} {loc_clause} site:metacareers.com/jobs'),
                ("Workday", f'{clean_role} {loc_clause} site:salesforce.wd12.myworkdayjobs.com'),
                ("Amazon", f'{clean_role} {loc_clause} site:amazon.jobs'),
                ("Microsoft", f'{clean_role} {loc_clause} site:careers.microsoft.com "/job/"')
            ]
        elif "amazon" in tb_lower:
            board_queries = [
                ("Amazon", f'{clean_role} {loc_clause} site:amazon.jobs/en/jobs'),
                ("Amazon", f'{clean_role} {loc_clause} site:amazon.jobs'),
                ("Amazon", f'"{clean_role}" {loc_clause} site:amazon.jobs')
            ]
        elif "microsoft" in tb_lower:
            board_queries = [
                ("Microsoft", f'{clean_role} {loc_clause} site:jobs.careers.microsoft.com'),
                ("Microsoft", f'{clean_role} {loc_clause} site:careers.microsoft.com "/job/"'),
                ("Microsoft", f'"{clean_role}" {loc_clause} site:careers.microsoft.com')
            ]
        elif "google" in tb_lower:
            board_queries = [
                ("Google", f'{clean_role} {loc_clause} "careers.google.com/jobs/results"'),
                ("Google", f'{clean_role} {loc_clause} site:google.com "about/careers"'),
                ("Google", f'"{clean_role}" {loc_clause} site:careers.google.com')
            ]
        elif "apple" in tb_lower:
            board_queries = [
                ("Apple", f'{clean_role} {loc_clause} site:jobs.apple.com details'),
                ("Apple", f'"{clean_role}" {loc_clause} site:jobs.apple.com')
            ]
        elif "meta" in tb_lower:
            board_queries = [
                ("Meta", f'{clean_role} {loc_clause} site:metacareers.com/jobs'),
                ("Meta", f'"{clean_role}" {loc_clause} site:metacareers.com')
            ]
        elif "smartrecruiters" in tb_lower:
            board_queries = [
                ("SmartRecruiters", f'{clean_role} {loc_clause} site:jobs.smartrecruiters.com'),
                ("SmartRecruiters", f'"{clean_role}" {loc_clause} site:jobs.smartrecruiters.com')
            ]
        elif "workday" in tb_lower:
            board_queries = [
                ("Workday", f'{clean_role} {loc_clause} "Job Description" site:myworkdayjobs.com'),
                ("Workday", f'{clean_role} {loc_clause} site:myworkdayjobs.com "/job/"'),
                ("Workday", f'"{clean_role}" {loc_clause} "Job Description" site:myworkdayjobs.com')
            ]
        elif "greenhouse" in tb_lower:
            board_queries = [
                ("Greenhouse", f'{clean_role} {loc_clause} site:boards.greenhouse.io'),
                ("Greenhouse", f'"{clean_role}" {loc_clause} site:boards.greenhouse.io'),
                ("Greenhouse", f'{clean_role} {loc_clause} site:job-boards.greenhouse.io')
            ]
        elif "lever" in tb_lower:
            board_queries = [
                ("Lever", f'{clean_role} {loc_clause} site:jobs.lever.co'),
                ("Lever", f'"{clean_role}" {loc_clause} site:jobs.lever.co'),
                ("Lever", f'{clean_role} {skill_clause} site:jobs.lever.co' if skill_clause else f'{clean_role} site:jobs.lever.co')
            ]
        elif "ashby" in tb_lower:
            board_queries = [
                ("Ashby", f'{clean_role} {loc_clause} site:jobs.ashbyhq.com'),
                ("Ashby", f'"{clean_role}" {loc_clause} site:jobs.ashbyhq.com')
            ]
        elif "linkedin" in tb_lower:
            board_queries = [
                ("LinkedIn", f'{clean_role} {loc_clause} site:linkedin.com/jobs/view'),
                ("LinkedIn", f'"{clean_role}" {loc_clause} site:linkedin.com/jobs/view'),
                ("LinkedIn", f'{clean_role} {loc_clause} site:in.linkedin.com/jobs/view'),
                ("LinkedIn", f'{clean_role} {loc_clause} site:linkedin.com "/jobs/view"'),
                ("LinkedIn", f'{clean_role} II {loc_clause} site:linkedin.com/jobs/view'),
                ("LinkedIn", f'SDE {loc_clause} site:linkedin.com/jobs/view')
            ]
        else:
            # All Sources: query each ATS host and top MNCs with individual requisition constraints
            board_queries = [
                ("Amazon", f'{clean_role} {loc_clause} site:amazon.jobs/en/jobs'),
                ("Workday", f'{clean_role} {loc_clause} "Job Description" site:myworkdayjobs.com'),
                ("Microsoft", f'{clean_role} {loc_clause} site:jobs.careers.microsoft.com'),
                ("SmartRecruiters", f'{clean_role} {loc_clause} site:jobs.smartrecruiters.com'),
                ("LinkedIn", f'{clean_role} {loc_clause} site:linkedin.com/jobs/view'),
                ("Google", f'{clean_role} {loc_clause} "careers.google.com/jobs/results"'),
                ("Apple", f'{clean_role} {loc_clause} site:jobs.apple.com details'),
                ("Meta", f'{clean_role} {loc_clause} site:metacareers.com/jobs'),
                ("Lever", f'{clean_role} {loc_clause} site:jobs.lever.co'),
                ("Greenhouse", f'{clean_role} {loc_clause} site:boards.greenhouse.io'),
                ("Workday", f'{clean_role} {loc_clause} site:myworkdayjobs.com "/job/"'),
                ("Ashby", f'{clean_role} {loc_clause} site:jobs.ashbyhq.com')
            ]

        candidates = []
        seen_urls = set()
        target_candidates_count = max(24, max_results * 4)

        if DDGS is not None:
            for source_name, q in board_queries:
                if len(candidates) >= target_candidates_count:
                    break
                # Try primary backend, with automatic fallback to Yahoo if rate-limited
                for backend_choice in ["auto", "yahoo"]:
                    try:
                        with DDGS(timeout=3.5) as ddgs:
                            raw = list(ddgs.text(q.strip(), max_results=12, backend=backend_choice))
                            for r in raw:
                                href = r.get("href") or r.get("url") or ""
                                title = r.get("title", "")
                                snippet = r.get("body") or r.get("snippet") or ""

                                # Normalize URL to prevent duplicates (e.g. Lever /apply suffix, tracking params)
                                norm_url = re.sub(r"/apply/?$", "", href).split("?")[0].rstrip("/")

                                # STRICT VALIDATION: Must match single requisition criteria
                                if norm_url and norm_url not in seen_urls and self._is_individual_job(href, title, snippet):
                                    seen_urls.add(norm_url)
                                    clean_t = self._clean_job_title(title, href, source_name)
                                    candidates.append({
                                        "title": clean_t,
                                        "url": norm_url,
                                        "snippet": snippet,
                                        "source": source_name
                                    })
                                    if len(candidates) >= target_candidates_count:
                                        break
                        if raw:
                            break
                    except Exception:
                        continue

        # Concurrent Active Liveness Verification:
        # Pre-flights candidate URLs in parallel to discard 404s, expired jobs, and redirect errors
        live_results = []
        if candidates:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                liveness_checks = list(executor.map(lambda c: self.verify_job_url_active(c["url"]), candidates))

            for cand, is_active in zip(candidates, liveness_checks):
                if is_active:
                    cand["is_verified_live"] = True
                    live_results.append(cand)
                    if len(live_results) >= max_results * 2:
                        break

        if live_results:
            return live_results

        # Fallback: Live Public Tech APIs (individual listings only)
        api_results = self._search_public_apis(clean_role, max_results=max_results)
        if api_results:
            return api_results

        # Return empty list if no individual requisitions match (never return generic directory search sets)
        return []

    def _verify_linkedin_active(self, url: str, headers: Dict[str, str], timeout: float = 4.0) -> bool:
        """
        Specialized active verifier for LinkedIn postings.
        Checks both LinkedIn Guest API and direct page HTML.
        Strictly requires the presence of an active Apply CTA button/link.
        When a posting is 'Not currently accepting applications' or closed, LinkedIn removes
        the Apply button from the DOM (empty CTA container).
        Also rejects postings containing closed/expired notices.
        """
        job_id_match = re.search(r"(\d{6,})", url)
        if not job_id_match:
            return False
        jid = job_id_match.group(1)

        dead_signals = [
            "not currently accepting applications",
            "no longer accepting applications",
            "not accepting applications",
            "applications are no longer being accepted",
            "applications are closed",
            "this job is closed",
            "this position has been closed",
            "this job is no longer available",
            "this position is no longer available",
            "position has been filled",
            "recruitment target, not an open vacancy",
            "planned position, not currently accepting",
            "planned not accepting applications",
            "top-card-layout__entity-status--closed",
            "closed-job-banner",
            "closed-tag",
            "entity-status--closed",
            "topcard__flavor--closed",
            "job-details-jobs-unified-top-card__closed-tag",
            "this job posting has expired"
        ]

        def _has_apply_button(html_text: str) -> bool:
            if not html_text or len(html_text) < 300:
                return False
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_text, "html.parser")
                apply_cta = soup.find(lambda tag: tag.name in ["button", "a"] and (
                    "top-card-layout__cta--primary" in tag.get("class", []) or
                    "apply-button" in tag.get("class", []) or
                    "apply-button--default" in tag.get("class", []) or
                    tag.get("data-tracking-control-name") in [
                        "public_jobs_apply-link",
                        "public_jobs_topcard-apply-button",
                        "public_jobs_apply-button-link",
                        "apply",
                        "easy-apply"
                    ] or
                    (any(w in tag.get_text(strip=True).lower() for w in ["apply", "easy apply", "apply now", "apply on company website"])
                     and not tag.get("disabled")
                     and "alert" not in tag.get_text(strip=True).lower()
                     and "similar" not in tag.get_text(strip=True).lower()
                     and "search" not in tag.get_text(strip=True).lower())
                ))
                return apply_cta is not None
            except Exception:
                return False

        # 1. Try Guest API (bypasses authwall and returns structured HTML)
        api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
        try:
            api_resp = requests.get(api_url, headers=headers, timeout=timeout)
            if api_resp.status_code in [404, 410]:
                return False
            if api_resp.status_code == 200:
                text_lower = api_resp.text.lower()
                for sig in dead_signals:
                    if sig in text_lower:
                        return False
                # Must affirmatively possess an active Apply button
                if not _has_apply_button(api_resp.text):
                    return False
                return True
        except Exception:
            pass

        # 2. Try direct job view URL as fallback
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if resp.status_code in [404, 410]:
                return False
            if resp.status_code == 200:
                text_lower = resp.text.lower()
                for sig in dead_signals:
                    if sig in text_lower:
                        return False
                if not _has_apply_button(resp.text):
                    return False
                return True
        except Exception:
            pass

        # If neither endpoint could affirmatively confirm an active Apply button, REJECT!
        return False

    def verify_job_url_active(self, url: str, timeout: float = 3.5) -> bool:
        """
        Actively verifies that a candidate job posting URL is live, open, and accepting applications.
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

        # LinkedIn postings get strict dedicated liveness inspection
        if "linkedin.com" in url.lower():
            return self._verify_linkedin_active(url, headers=headers, timeout=timeout)

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
                "not currently accepting applications",
                "not accepting applications",
                "applications are no longer being accepted",
                "applications are closed",
                "this job is closed",
                "this position has been closed",
                "job is not found",
                "job not found",
                "position has been filled",
                "job requisition no longer open",
                "job requisition is no longer open",
                "this posting has expired",
                "the job you are looking for is no longer open",
                "recruitment target, not an open vacancy",
                "planned position, not currently accepting",
                "top-card-layout__entity-status--closed",
                "closed-job-banner",
                "closed-tag",
                "entity-status--closed",
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
            return False

    def _is_individual_job(self, url: str, title: str, snippet: str = "") -> bool:
        """
        STRICT VALIDATION:
        Returns True ONLY if the URL and title represent a single individual job posting.
        Returns False for company portal landing pages, search forms, directory sets,
        or postings that explicitly indicate in title/snippet that applications are closed.
        """
        url_lower = url.lower()
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        full_meta = f"{title_lower} {snippet_lower}"

        # 0. Reject postings that explicitly advertise they are closed or not accepting applications
        dead_meta_patterns = [
            "no longer accepting applications",
            "not currently accepting applications",
            "not accepting applications",
            "applications are no longer being accepted",
            "applications are closed",
            "this job is closed",
            "recruitment target, not an open vacancy",
            "planned position, not currently accepting"
        ]
        for dp in dead_meta_patterns:
            if dp in full_meta:
                return False

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

        # LinkedIn: MUST have '/jobs/view/[slug-]id'
        if "linkedin.com" in url_lower:
            # Must contain an individual job view path with numeric ID (at least 6 digits)
            if not re.search(r"linkedin\.com/jobs/view/[^?]*\d{6,}", url_lower):
                return False
            # Reject directory searches and title listings
            if any(p in url_lower for p in ["/jobs/search", "/jobs/collections", "-jobs-", "/jobs/browse"]):
                return False
            return True

        # Indeed: MUST have '/viewjob'
        if "indeed.com" in url_lower:
            if "/viewjob" not in url_lower:
                return False
            return True

        # SmartRecruiters: MUST have company and job requisition path
        if "smartrecruiters.com" in url_lower:
            if re.search(r"jobs\.smartrecruiters\.com/[^/]+/[^/?]+", url_lower):
                return True
            return False

        # Amazon Careers: MUST have /jobs/<id>
        if "amazon.jobs" in url_lower:
            if re.search(r"amazon\.jobs/(?:[^/]+/)*jobs/\d+", url_lower):
                return True
            return False

        # Microsoft Careers: MUST have /job/<id> or /share/<id>
        if "careers.microsoft.com" in url_lower:
            if re.search(r"careers\.microsoft\.com/(?:[^/]+/)*(?:job|share)/\d+", url_lower):
                return True
            return False

        # Google Careers: MUST have /jobs/results/<id>
        if "google.com/about/careers" in url_lower or "careers.google.com" in url_lower:
            if re.search(r"(?:google\.com/about/careers/applications/jobs/results|careers\.google\.com/jobs/results)/\d+", url_lower):
                return True
            return False

        # Apple Jobs: MUST have /details/<id>
        if "jobs.apple.com" in url_lower:
            if re.search(r"jobs\.apple\.com/(?:[^/]+/)*details/\d+", url_lower):
                return True
            return False

        # Meta Careers: MUST have /jobs/<id>
        if "metacareers.com" in url_lower or "careers.facebook.com" in url_lower:
            if re.search(r"(?:metacareers|careers\.facebook)\.com/jobs/\d+", url_lower):
                return True
            return False

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
        cleaned = re.sub(r"\s*-\s*SmartRecruiters.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*\|\s*SmartRecruiters.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*Logo$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*Job ID:\s*\d+.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*\|\s*Microsoft Careers.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*jobs\.careers\.microsoft\.com.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*Google Careers.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*-\s*Jobs at Apple.*$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*\|\s*Meta Careers.*$", "", cleaned, flags=re.I)

        # Prepend or append verified MNC / ATS company names
        url_lower = url.lower()
        if "amazon.jobs" in url_lower and "amazon" not in cleaned.lower():
            cleaned = f"{cleaned} at Amazon"
        elif "careers.microsoft.com" in url_lower and "microsoft" not in cleaned.lower():
            cleaned = f"{cleaned} at Microsoft"
        elif ("careers.google.com" in url_lower or "google.com/about/careers" in url_lower) and "google" not in cleaned.lower():
            cleaned = f"{cleaned} at Google"
        elif "jobs.apple.com" in url_lower and "apple" not in cleaned.lower():
            cleaned = f"{cleaned} at Apple"
        elif ("metacareers.com" in url_lower or "careers.facebook.com" in url_lower) and "meta" not in cleaned.lower():
            cleaned = f"{cleaned} at Meta"
        elif "myworkdayjobs.com" in url_lower:
            match = re.search(r"https?://([^.]+)\.[^/]*myworkdayjobs\.com", url, re.I)
            if match:
                company_name = match.group(1).title()
                if company_name.lower() not in cleaned.lower():
                    cleaned = f"{cleaned} at {company_name}"

        return cleaned.strip()

    def score_job_against_profile(
        self,
        job: Dict[str, Any],
        candidate_profile: Dict[str, Any],
        target_tier: int = -1
    ) -> Dict[str, Any]:
        """
        Scores a job result against the candidate's master profile, evaluating both
        tech stack overlap and seniority alignment.
        """
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
        job_title_lower = job.get("title", "").lower()
        if any(w in job_title_lower for w in ["software", "developer", "engineer", "cloud", "platform", "backend"]):
            title_bonus += 15

        # Seniority Alignment Evaluation
        job_sen = self.detect_job_seniority(job.get("title", ""), job.get("snippet", ""))
        seniority_bonus = 0
        if target_tier != -1:
            tier_diff = job_sen["tier"] - target_tier
            if tier_diff == 0:
                seniority_bonus = 20
                seniority_fit = "Aligned Level"
            elif tier_diff == 1:
                seniority_bonus = 5
                seniority_fit = "Stretch Level (+1)"
            elif tier_diff == -1:
                seniority_bonus = 10
                seniority_fit = "Viable Level (-1)"
            else:
                seniority_bonus = -30
                seniority_fit = "Experience Mismatch"
        else:
            seniority_fit = "General Fit"

        skill_score = min(60, len(matched_skills) * 16)
        total_score = max(20, min(98, 25 + title_bonus + seniority_bonus + skill_score))

        if total_score >= 78:
            fit_tier = "High Match"
            badge_color = "green"
        elif total_score >= 58:
            fit_tier = "Moderate Match"
            badge_color = "blue"
        else:
            fit_tier = "Potential Match"
            badge_color = "orange"

        return {
            "match_score": total_score,
            "fit_tier": fit_tier,
            "badge_color": badge_color,
            "seniority_level": job_sen["label"],
            "seniority_fit": seniority_fit,
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
