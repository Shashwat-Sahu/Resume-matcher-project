"""
Resume Tailorer Engine.
Uses local Llama AI to synthesize the Master Resume and Target Job Description
into an ATS-compliant, recruiter-compelling tailored resume and interview preparation guide.
"""

import json
import logging
import re
from typing import Dict, Any, Optional

from modules.llm_client import LocalLLMClient

logger = logging.getLogger(__name__)

TAILOR_SYSTEM_PROMPT = """You are an Elite Executive Resume Architect and ATS Optimization Strategist.
Your goal is to tailor the candidate's Master Resume for a specific target job posting to maximize ATS parsing scores and win interviews with hiring managers.

CRITICAL ATS & RECRUITER RULES:
1. STRICT TRUTH-PRESERVING: NEVER fabricate non-existent jobs, degrees, or imaginary companies. Work strictly from the candidate's actual background, highlighting, reframing, and prioritizing authentic accomplishments.
2. SINGLE-COLUMN ATS HIERARCHY: Structure strictly in clean Markdown using standard headers:
   # [Full Name]
   [Contact Line: Phone | Email | Location | LinkedIn | Portfolio]
   ## Professional Summary
   ## Core Technical Skills
   ## Professional Experience
   ## Key Projects
   ## Education & Certifications
3. THREE-LAYER KEYWORD INTEGRATION:
   - Layer 1 (Summary): Embed target job title and top 3 must-have tech skills + years of experience.
   - Layer 2 (Skills): Organize into clear categories (Languages, Frameworks, Cloud, Databases, Tools) matching employer terminology.
   - Layer 3 (Experience Bullets): Weave target keywords naturally into achievement bullets.
4. GOOGLE XYZ / STAR FORMULA:
   - Format bullets: Accomplished [X] as measured by [Y] by doing [Z].
   - Start with punchy action verbs (Architected, Engineered, Spearheaded, Automated, Scaled, Streamlined).
   - Preserve or enhance quantifiable metrics (%, $, scale, users, latency, throughput).
5. DATE & LOCATION CONSISTENCY:
   - Use 'Month YYYY – Month YYYY' or 'Month YYYY – Present'.
"""

class ResumeTailorer:
    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.llm = llm_client or LocalLLMClient()

    def generate_tailored_resume(
        self,
        master_profile: Dict[str, Any],
        raw_master_text: str,
        job_data: Dict[str, Any],
        ats_analysis: Dict[str, Any],
        page_length: str = "auto"
    ) -> str:
        """
        Generates fully tailored Markdown resume using local Llama model with page length constraints.
        """
        job_title = job_data.get("title", "Target Position")
        company = job_data.get("company", "Target Company")
        missing_kw = ats_analysis.get("keyword_analysis", {}).get("missing_critical_keywords", [])[:10]
        matched_kw = ats_analysis.get("keyword_analysis", {}).get("matched_keywords", [])

        if page_length == "1-page":
            length_instruction = (
                "PAGE LENGTH CONSTRAINT: STRICT 1-PAGE BUDGET.\n"
                "- Keep Professional Summary to exactly 2 concise, high-impact sentences.\n"
                "- Select and refine ONLY the top 3 most quantified, relevant bullets per job.\n"
                "- Group skills into 3-4 dense, single-line categories.\n"
                "- Keep the entire output concise so it fits cleanly on exactly ONE printed page."
            )
        elif page_length == "2-page":
            length_instruction = (
                "PAGE LENGTH CONSTRAINT: COMPREHENSIVE 2-PAGE SENIOR BUDGET.\n"
                "- Provide an executive 3-4 line summary.\n"
                "- Detail 4-5 quantified accomplishment bullets per role with architecture, metrics, and scale.\n"
                "- Include extensive technical skills, projects, and domain expertise."
            )
        else:
            length_instruction = "PAGE LENGTH CONSTRAINT: Natural balanced single-column layout."

        user_prompt = f"""
TARGET ROLE: {job_title} at {company}

{length_instruction}

REQUIRED SKILLS & KEYWORDS TO INCORPORATE:
Matched in Profile: {', '.join(matched_kw) if matched_kw else 'N/A'}
Priority Missing Keywords to integrate where candidate has relevant context: {', '.join(missing_kw) if missing_kw else 'N/A'}

TARGET JOB DESCRIPTION SUMMARY:
Required Hard Skills: {job_data.get('required_hard_skills', [])}
Tools & Frameworks: {job_data.get('tools_and_frameworks', [])}
Core Responsibilities: {job_data.get('core_responsibilities', [])[:5]}

CANDIDATE MASTER RESUME DATA:
{json.dumps(master_profile, indent=2)}

ORIGINAL MASTER RESUME TEXT (FOR CONTEXT & METRICS):
{raw_master_text[:6000]}

TASK:
Generate a complete, production-ready, ATS-optimized single-column resume in Markdown.
- Header: Name, Contact Info in the main body (Phone | Email | Location | LinkedIn | GitHub).
- Professional Summary: Tailored specifically to {job_title}, spotlighting matching strengths.
- Technical Skills: Grouped logically, prioritizing employer's required tech stack.
- Professional Experience: Reframed with strong action verbs and Google XYZ metrics, elevating projects/responsibilities most relevant to {job_title}.
- Projects & Education: Highlight tech stack and coursework relevant to this position.

Return ONLY the resume markdown without conversational preamble or postscript.
"""
        try:
            tailored_md = self.llm.generate(prompt=user_prompt, system_prompt=TAILOR_SYSTEM_PROMPT)
            return self._clean_markdown(tailored_md)
        except Exception as e:
            logger.warning(f"LLM tailoring failed or offline ({e}). Generating high-quality rule-based fallback.")
            return self._fallback_tailored_resume(master_profile, job_data, matched_kw, missing_kw)

    def generate_interview_prep(
        self,
        tailored_resume_md: str,
        job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates tactical interview preparation tips, likely questions, and STAR answer outlines.
        """
        system_prompt = (
            "You are an Executive Hiring Manager and Technical Interviewer.\n"
            "Analyze the tailored resume and target job requirements to predict top interview questions, "
            "potential gap scrutiny, and strategic talking points."
        )

        user_prompt = f"""
TARGET JOB:
Role: {job_data.get('title', 'Role')}
Required Skills: {job_data.get('required_hard_skills', [])}
Responsibilities: {job_data.get('core_responsibilities', [])[:4]}

TAILORED RESUME:
{tailored_resume_md[:4000]}

Provide an interview strategy in JSON format with these exact keys:
{{
  "elevator_pitch": "A 60-second 'Tell me about yourself' pitch specifically framed for this role.",
  "top_technical_questions": [
    {{"question": "", "why_asked": "", "recommended_talking_points": ""}}
  ],
  "top_behavioral_questions": [
    {{"question": "", "star_approach": ""}}
  ],
  "potential_red_flags_or_gaps": [
    {{"gap": "", "how_to_bridge": ""}}
  ],
  "questions_to_ask_interviewer": []
}}

Return ONLY valid JSON.
"""
        try:
            return self.llm.generate_json(prompt=user_prompt, system_prompt=system_prompt)
        except Exception as e:
            return {
                "elevator_pitch": f"Passionate professional with deep experience in {', '.join(job_data.get('required_hard_skills', [])[:3])}, focused on driving scalable impact and operational excellence.",
                "top_technical_questions": [
                    {
                        "question": f"How do you design and scale applications using {job_data.get('required_hard_skills', ['your core stack'])[0]}?",
                        "why_asked": "Assesses foundational architecture and problem-solving depth.",
                        "recommended_talking_points": "Focus on trade-offs, scalability bottlenecks, and monitoring."
                    }
                ],
                "top_behavioral_questions": [
                    {
                        "question": "Tell me about a time you had to adapt quickly to an ambiguous project requirement.",
                        "star_approach": "Situation: tight deadline or shifting specs. Task: deliver MVP. Action: communicated with stakeholders and prioritized core features. Result: shipped on time with positive feedback."
                    }
                ],
                "potential_red_flags_or_gaps": [
                    {
                        "gap": "Specific proprietary internal tools from JD not on resume",
                        "how_to_bridge": "Highlight fast learning curve and parallel open-source technologies."
                    }
                ],
                "questions_to_ask_interviewer": [
                    "What does success look like in the first 90 days for this role?",
                    "What are the biggest architectural or operational hurdles the team is solving right now?"
                ]
            }

    def _clean_markdown(self, text: str) -> str:
        """Extracts strictly markdown content, removing preambles and code fences."""
        text = text.strip()
        # Look for code block fences
        match = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # If it starts with a fence without closing or partial
        if text.startswith("```markdown"):
            text = text[11:]
        elif text.startswith("```md"):
            text = text[5:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _fallback_tailored_resume(
        self,
        master: Dict[str, Any],
        job: Dict[str, Any],
        matched_kw: list,
        missing_kw: list
    ) -> str:
        """Rule-based generator if LLM is temporarily offline."""
        contact = master.get("contact", {})
        name = contact.get("name", "Candidate Name")
        contact_line = " | ".join(filter(None, [
            contact.get("phone"),
            contact.get("email"),
            contact.get("location"),
            contact.get("linkedin"),
            contact.get("github")
        ]))

        target_title = job.get("title") or "Software Engineering Professional"

        md_parts = [
            f"# {name}",
            f"{contact_line}\n",
            "## Professional Summary",
            f"Results-driven {target_title} with comprehensive experience across {', '.join(matched_kw[:4]) if matched_kw else 'software systems'}. "
            f"Proven track record of architecting scalable solutions, optimizing performance, and collaborating across cross-functional teams to deliver high-impact products.",
            "\n## Technical Skills"
        ]

        # Skills categories
        skills = master.get("skills", {})
        if isinstance(skills, dict):
            for cat, items in skills.items():
                if items:
                    cat_name = cat.replace("_", " ").title()
                    md_parts.append(f"- **{cat_name}:** {', '.join(items)}")
        elif isinstance(skills, list):
            md_parts.append(f"- **Core Skills:** {', '.join(skills)}")

        # Experience
        md_parts.append("\n## Professional Experience")
        for exp in master.get("experience", []):
            comp = exp.get("company", "Company")
            title = exp.get("title", "Role")
            dates = exp.get("dates", "Dates")
            loc = exp.get("location", "")
            header = f"### {title} | {comp}"
            if loc or dates:
                header += f" ({dates}{f', {loc}' if loc else ''})"
            md_parts.append(header)
            for b in exp.get("bullets", []):
                md_parts.append(f"- {b}")
            md_parts.append("")

        # Projects
        if master.get("projects"):
            md_parts.append("## Key Projects")
            for proj in master.get("projects", []):
                pname = proj.get("name", "Project")
                tech = ", ".join(proj.get("tech_stack", []))
                md_parts.append(f"### {pname}{f' ({tech})' if tech else ''}")
                for b in proj.get("bullets", []):
                    md_parts.append(f"- {b}")
                md_parts.append("")

        # Education
        if master.get("education"):
            md_parts.append("## Education")
            for edu in master.get("education", []):
                deg = edu.get("degree", "Degree")
                inst = edu.get("institution", "Institution")
                grad = edu.get("graduation_date", "")
                md_parts.append(f"- **{deg}**, {inst}{f' ({grad})' if grad else ''}")

        return "\n".join(md_parts)
