"""
Job Searcher module.
Searches the web for live openings matching candidate profile/skills.
Uses modern 'ddgs' engine with automatic warning suppression,
resilient multi-tier fallback (live job APIs & clean web search),
and direct portal deep-linking (LinkedIn, Indeed, Greenhouse, Google Jobs).
"""

import re
import urllib.parse
import warnings
import logging
from typing import List, Dict, Any, Optional
import requests

# Suppress the package rename RuntimeWarning from duckduckgo_search
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="ddgs")

# Silence noisy HTTP/backend logs from ddgs and primp
logging.getLogger("primp").setLevel(logging.WARNING)
logging.getLogger("ddgs").setLevel(logging.WARNING)
logging.getLogger("duckduckgo_search").setLevel(logging.WARNING)

# Try modern ddgs first, fallback to duckduckgo_search
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

    def search_jobs(self, query: str, max_results: int = 6) -> List[Dict[str, str]]:
        """
        Executes robust search for job listings across multiple tiers:
        Tier 1: Clean web search via DDGS
        Tier 2: Direct public job board API (Arbeitnow / Jobicy)
        Tier 3: Formatted direct portal links (LinkedIn, Indeed, Google Jobs)
        """
        results = []

        # Sanitize query: strip problematic boolean OR operators that crash search backends
        sanitized_query = self._sanitize_query(query)

        # Tier 1: Try DDGS with sanitized query
        if DDGS is not None:
            try:
                with DDGS() as ddgs:
                    raw_results = list(ddgs.text(sanitized_query, max_results=max_results))
                    for r in raw_results:
                        href = r.get("href") or r.get("url") or ""
                        title = r.get("title", "")
                        body = r.get("body") or r.get("snippet") or ""
                        if href and title:
                            results.append({
                                "title": title,
                                "url": href,
                                "snippet": body,
                                "source": self._detect_source(href)
                            })
                    if results:
                        return results
            except Exception:
                pass  # Fall through to Tier 2

        # Tier 2: Public Job Board APIs (Arbeitnow / Jobicy)
        api_results = self._search_public_apis(sanitized_query, max_results=max_results)
        if api_results:
            return api_results

        # Tier 3: Direct portal link generator
        return self._generate_portal_links(query)

    def _sanitize_query(self, query: str) -> str:
        """Removes complex boolean operators that cause search engines to return empty documents."""
        clean = re.sub(r"\bOR\b", " ", query, flags=re.I)
        clean = re.sub(r"site:[^\s]+", " ", clean)  # Remove rigid site: filters that fail in Bing
        clean = " ".join(clean.split())
        if "job" not in clean.lower() and "hiring" not in clean.lower():
            clean += " jobs"
        return clean.strip()

    def _detect_source(self, url: str) -> str:
        url_lower = url.lower()
        if "greenhouse.io" in url_lower:
            return "Greenhouse"
        elif "lever.co" in url_lower:
            return "Lever"
        elif "workday" in url_lower:
            return "Workday"
        elif "linkedin.com" in url_lower:
            return "LinkedIn"
        elif "indeed.com" in url_lower:
            return "Indeed"
        elif "naukri.com" in url_lower:
            return "Naukri"
        return "Company / Job Board"

    def _search_public_apis(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Queries live public tech job endpoints as reliable fallback."""
        results = []
        keywords = [k.lower() for k in query.split() if len(k) > 2 and k.lower() not in ["jobs", "hiring", "role"]]

        # Try Arbeitnow
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
                            "title": f"{title} - {job.get('company_name', '')}",
                            "url": job.get("url", ""),
                            "snippet": f"Location: {job.get('location', 'Remote')} | Tags: {', '.join(job.get('tags', [])[:3])}",
                            "source": "Arbeitnow (Live Tech Board)"
                        })
                        if len(results) >= max_results:
                            return results
        except Exception:
            pass

        return results

    def _generate_portal_links(self, query: str) -> List[Dict[str, str]]:
        """Generates pre-filled 1-click links to major job boards if web scraper is blocked."""
        encoded = urllib.parse.quote(query)
        return [
            {
                "title": f"Search '{query}' on LinkedIn Jobs",
                "url": f"https://www.linkedin.com/jobs/search/?keywords={encoded}",
                "snippet": "View latest openings with 1-click apply on LinkedIn.",
                "source": "LinkedIn Portal"
            },
            {
                "title": f"Search '{query}' on Google Jobs",
                "url": f"https://www.google.com/search?q={encoded}+jobs&ibp=htl;jobs",
                "snippet": "Aggregated job postings from company career pages across Google.",
                "source": "Google Jobs"
            },
            {
                "title": f"Search '{query}' on Indeed",
                "url": f"https://www.indeed.com/jobs?q={encoded}",
                "snippet": "Explore verified employer postings on Indeed.",
                "source": "Indeed"
            }
        ]
