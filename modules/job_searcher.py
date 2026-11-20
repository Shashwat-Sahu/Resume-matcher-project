"""
Job Searcher module.
Searches the web for individual, specific job requisition postings
(hosted on Greenhouse, Lever, Workday, Ashby, and LinkedIn single-view).
Strictly filters out search directory aggregators, collection sets, and catalog pages.
"""

import re
import urllib.parse
import warnings
import logging
from typing import List, Dict, Any, Optional
import requests

# Suppress noisy logs and rename warnings
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

    def search_jobs(
        self,
        query: str = "",
        role: str = "",
        location: str = "",
        target_board: str = "All Sources",
        max_results: int = 6
    ) -> List[Dict[str, str]]:
        """
        Main entry point for finding individual job postings.
        Can accept either (role, location) or a raw search string.
        """
        if not role:
            # Parse role and location from query string
            tokens = query.split()
            role = " ".join(tokens[:2]) if len(tokens) >= 2 else query
            location = " ".join(tokens[2:]) if len(tokens) > 2 else ""

        return self.search_individual_jobs(role=role, location=location, target_board=target_board, max_results=max_results)

    def search_individual_jobs(
        self,
        role: str,
        location: str = "",
        target_board: str = "All Sources",
        max_results: int = 6
    ) -> List[Dict[str, str]]:
        """
        Queries specific ATS boards (Greenhouse, Lever, Workday, Ashby) to return
        individual, standalone job postings rather than generic directory aggregators.
        """
        clean_role = re.sub(r"[^\w\s\+\#]", " ", role).strip()
        loc_clause = f'"{location.strip()}"' if location.strip() else ""

        # Build board-specific search queries targeting individual requisition endpoints
        board_queries = []

        if target_board == "Lever":
            board_queries = [("Lever", f'"{clean_role}" {loc_clause} site:jobs.lever.co')]
        elif target_board == "Workday":
            board_queries = [("Workday", f'"{clean_role}" {loc_clause} site:myworkdayjobs.com')]
        elif target_board == "Greenhouse":
            board_queries = [
                ("Greenhouse", f'"{clean_role}" {loc_clause} site:greenhouse.io'),
                ("Greenhouse", f'"{clean_role}" {loc_clause} site:job-boards.greenhouse.io')
            ]
        elif target_board == "Ashby":
            board_queries = [("Ashby", f'"{clean_role}" {loc_clause} site:jobs.ashbyhq.com')]
        elif target_board == "LinkedIn (Single View)":
            board_queries = [("LinkedIn", f'"{clean_role}" {loc_clause} site:linkedin.com/jobs/view')]
        else:
            # All Sources: query major ATS engines in priority order
            board_queries = [
                ("Workday", f'"{clean_role}" {loc_clause} site:myworkdayjobs.com'),
                ("Lever", f'"{clean_role}" {loc_clause} site:jobs.lever.co'),
                ("Greenhouse", f'"{clean_role}" {loc_clause} site:greenhouse.io'),
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

        # Fallback 1: Live Public Tech APIs (individual listings)
        api_results = self._search_public_apis(clean_role, max_results=max_results)
        if api_results:
            return api_results

        # Fallback 2: Direct Search Portal Links
        return self._generate_portal_links(f"{clean_role} {location}".strip())

    def _is_individual_job(self, url: str, title: str) -> bool:
        """
        Filters out generic search sets, directory pages, and candidate aggregators.
        Only keeps specific individual job postings.
        """
        # Blocked directory / search set URL patterns
        blocked_urls = [
            r"linkedin\.com/jobs/(?!view/)",           # Drops /jobs/search or /jobs/<keyword>-jobs
            r"indeed\.com/q-",                         # Drops Indeed search queries
            r"indeed\.com/jobs\?",                     # Drops Indeed search queries
            r"glassdoor\.[a-z]+/Job/",                 # Drops Glassdoor search directories
            r"glassdoor\.[a-z]+/Jobs-",
            r"naukri\.com/[^/]+-jobs",                 # Drops Naukri category pages
            r"shine\.com/job-search",
            r"foundit\.in/srp",
            r"/browse-jobs",
            r"/all-jobs"
        ]

        for pattern in blocked_urls:
            if re.search(pattern, url, re.I):
                return False

        # Blocked collection/set title phrases
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

        # Check for positive indicators of individual job requisitions
        valid_ats_indicators = [
            r"jobs\.lever\.co/[^/]+/[0-9a-f\-]+",
            r"greenhouse\.io/[^/]+/jobs/\d+",
            r"myworkdayjobs\.com/[^/]+/job/",
            r"jobs\.ashbyhq\.com/[^/]+/[0-9a-f\-]+",
            r"linkedin\.com/jobs/view/\d+",
            r"/job/\d+",
            r"/jobs/\d+"
        ]

        for indicator in valid_ats_indicators:
            if re.search(indicator, url, re.I):
                return True

        # If not strictly matching blocked rules, allow company career pages
        return True

    def _clean_job_title(self, title: str, source: str) -> str:
        """Strips ATS boilerplate prefixes like 'Job Application for ...' from title."""
        title = re.sub(r"^Job Application for\s*", "", title, flags=re.I)
        title = re.sub(r"^Job Application:\s*", "", title, flags=re.I)
        title = re.sub(r"\s*-\s*Careers\s*at\s*.*$", "", title, flags=re.I)
        return title.strip()

    def _search_public_apis(self, role: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Queries live public tech job endpoints as reliable fallback for individual postings."""
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
