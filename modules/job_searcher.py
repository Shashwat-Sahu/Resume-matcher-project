"""
Job Searcher module.
Searches the web for live openings matching candidate profile/skills.
Queries ATS job boards (Greenhouse, Lever, Workday, LinkedIn, Indeed)
allowing the candidate to select a live posting with one click.
"""

import re
import urllib.parse
from typing import List, Dict, Any, Optional
import requests

class JobSearcher:
    def __init__(self):
        pass

    def build_search_queries(self, candidate_profile: Dict[str, Any], desired_title: str = "", location: str = "") -> List[str]:
        """Formulates targeted search queries for ATS boards (Lever, Greenhouse, Workday)."""
        title = desired_title or candidate_profile.get("contact", {}).get("title") or "Software Engineer"
        skills = []
        skills_obj = candidate_profile.get("skills", {})
        if isinstance(skills_obj, dict):
            for cat, items in skills_obj.items():
                if isinstance(items, list):
                    skills.extend(items[:2])
        elif isinstance(skills_obj, list):
            skills = skills_obj[:4]

        top_tech = " ".join(skills[:3]) if skills else "Python AWS"
        loc_str = f"\"{location}\"" if location else ""

        queries = [
            f"{title} {top_tech} site:boards.greenhouse.io {loc_str}".strip(),
            f"{title} {top_tech} site:jobs.lever.co {loc_str}".strip(),
            f"{title} {top_tech} (site:myworkdayjobs.com OR site:linkedin.com/jobs) {loc_str}".strip(),
            f"hiring {title} {top_tech} {loc_str}".strip()
        ]
        return queries

    def search_jobs(self, query: str, max_results: int = 6) -> List[Dict[str, str]]:
        """
        Executes web search for job listings.
        Uses duckduckgo_search if available, with robust fallback.
        """
        results = []

        # Try duckduckgo_search library
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                ddg_results = ddgs.text(query, max_results=max_results)
                for r in ddg_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                        "source": "Web / ATS Board"
                    })
                if results:
                    return results
        except Exception:
            pass

        # Fallback via direct requests to DuckDuckGo HTML / instant API
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", class_="result__url")
                snippets = soup.find_all("a", class_="result__snippet")
                titles = soup.find_all("a", class_="result__title")

                for i in range(min(max_results, len(titles))):
                    href = titles[i].get("href", "")
                    # Extract redirect url if needed
                    if "uddg=" in href:
                        match = re.search(r"uddg=([^&]+)", href)
                        if match:
                            href = urllib.parse.unquote(match.group(1))

                    results.append({
                        "title": titles[i].get_text(strip=True),
                        "url": href,
                        "snippet": snippets[i].get_text(strip=True) if i < len(snippets) else "",
                        "source": "DuckDuckGo"
                    })
        except Exception:
            pass

        return results
