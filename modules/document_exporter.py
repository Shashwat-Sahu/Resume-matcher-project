"""
Document Exporter module.
Generates 100% ATS-compliant single-column formats:
- Clean Markdown (.md)
- Workday/Greenhouse certified Word DOCX (.docx)
- Text-layer selectable PDF (.pdf) with ATS Templates:
  * Jake's Tech Standard (Single-Column Sans-Serif - Google/Tech standard)
  * Harvard Ivy Standard (Classic Serif - Times New Roman / Finance / Executive)
  * Modern Minimalist (FAANG Accent Blue)
  Supports Page Length budgets: Strict 1-Page vs Standard 2-Page vs Auto.
"""

import os
import re
from typing import Optional

try:
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
except ImportError:
    docx = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
except ImportError:
    SimpleDocTemplate = None


class DocumentExporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_markdown(self, markdown_text: str, filename: str = "tailored_resume.md") -> str:
        """Saves clean markdown resume."""
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        return path

    def export_docx(self, markdown_text: str, filename: str = "tailored_resume.docx", page_length: str = "auto") -> str:
        """
        Builds a strictly ATS-compliant single-column Word document.
        - Standard 0.75-inch (or 0.5-inch for 1-page) margins
        - Calibri typography
        - No tables, no headers/footers (Workday strips them)
        - Native Word bullet lists
        """
        if not docx:
            raise ImportError("python-docx is required for DOCX export. Run: pip install python-docx")

        doc = docx.Document()
        margin = 0.5 if page_length == "1-page" else 0.75

        for section in doc.sections:
            section.top_margin = Inches(margin)
            section.bottom_margin = Inches(margin)
            section.left_margin = Inches(margin)
            section.right_margin = Inches(margin)
            section.header.is_linked_to_previous = False
            section.footer.is_linked_to_previous = False

        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(9.5 if page_length == "1-page" else 10.5)
        font.color.rgb = RGBColor(30, 30, 30)

        lines = markdown_text.split("\n")

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Heading 1: Candidate Name
            if line.startswith("# "):
                name_text = line[2:].strip()
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(2)
                run = p.add_run(name_text)
                run.bold = True
                run.font.size = Pt(18 if page_length == "1-page" else 20)
                run.font.color.rgb = RGBColor(15, 23, 42)

            # Heading 2: Section Header
            elif line.startswith("## "):
                sec_text = line[3:].strip()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(8 if page_length == "1-page" else 11)
                p.paragraph_format.space_after = Pt(2 if page_length == "1-page" else 3)
                p.paragraph_format.keep_with_next = True
                run = p.add_run(sec_text.upper())
                run.bold = True
                run.font.size = Pt(11 if page_length == "1-page" else 12)
                run.font.color.rgb = RGBColor(30, 58, 138)
                self._add_bottom_border(p)

            # Heading 3: Role / Company / Dates
            elif line.startswith("### "):
                role_text = line[4:].strip()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4 if page_length == "1-page" else 5)
                p.paragraph_format.space_after = Pt(1 if page_length == "1-page" else 2)
                p.paragraph_format.keep_with_next = True
                run = p.add_run(role_text)
                run.bold = True
                run.font.size = Pt(9.5 if page_length == "1-page" else 10.5)

            # Bullet points
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = line[2:].strip()
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_before = Pt(0.5 if page_length == "1-page" else 1)
                p.paragraph_format.space_after = Pt(1 if page_length == "1-page" else 1.5)
                p.paragraph_format.line_spacing = 1.1 if page_length == "1-page" else 1.15
                self._format_bold_spans(p, bullet_text)

            # Regular paragraph
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(1.5 if page_length == "1-page" else 2)
                p.paragraph_format.space_after = Pt(2 if page_length == "1-page" else 2.5)
                p.paragraph_format.line_spacing = 1.1 if page_length == "1-page" else 1.15

                if "|" in line and ("@" in line or "linkedin" in line.lower() or "phone" in line.lower()):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_after = Pt(5 if page_length == "1-page" else 7)

                self._format_bold_spans(p, line)

        output_path = os.path.join(self.output_dir, filename)
        doc.save(output_path)
        return output_path

    def export_pdf(
        self,
        markdown_text: str,
        filename: str = "tailored_resume.pdf",
        candidate_name: str = "Candidate",
        job_title: str = "",
        company: str = "",
        job_url: str = "",
        template: str = "jake",
        page_length: str = "auto"
    ) -> str:
        """
        Generates a 100% ATS-compliant text-layer PDF with selectable text:
        Templates:
          - 'jake': Tech standard, clean sans-serif (Helvetica), high-density
          - 'harvard': Classic Ivy League serif (Times-Roman), formal divider rules
          - 'modern': Minimalist FAANG accent (Navy/Slate headers)
        Page Length Budgets:
          - '1-page': Tight margins (0.5"), compact typography (8.5-9pt), tuned for 1 page
          - '2-page' / 'auto': Standard margins (0.75"), 9.5-10pt body font
        """
        if not SimpleDocTemplate:
            raise ImportError("reportlab is required for PDF export. Run: pip install reportlab")

        output_path = os.path.join(self.output_dir, filename)

        # Page margins
        if page_length == "1-page":
            margin = 36.0  # 0.5 inch for strict 1-page density
            v_margin = 32.0
            body_size = 8.5
            body_leading = 11.2
            name_size = 16.0
            name_leading = 19.0
            sec_size = 10.0
            sec_leading = 12.5
            bullet_space = 1.0
            sec_space_before = 5.0
            sec_space_after = 2.0
        else:
            margin = 54.0  # 0.75 inch standard ATS margin
            v_margin = 42.0
            body_size = 9.5
            body_leading = 13.0
            name_size = 19.0
            name_leading = 23.0
            sec_size = 11.0
            sec_leading = 14.0
            bullet_space = 2.0
            sec_space_before = 8.0
            sec_space_after = 3.0

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=v_margin,
            bottomMargin=v_margin
        )

        # Metadata
        doc.title = f"{candidate_name} - {job_title or 'Resume'}"
        doc.author = candidate_name
        doc.subject = f"Tailored Resume for {job_title} at {company} ({job_url})"
        doc.creator = f"Resume Matcher Pro (Template: {template.title()}, Budget: {page_length})"

        styles = getSampleStyleSheet()

        # Font selection based on template
        if template == "harvard":
            main_font = "Times-Roman"
            bold_font = "Times-Bold"
            accent_color = colors.HexColor("#111827")  # Deep charcoal
            bar_color = colors.HexColor("#94A3B8")
        elif template == "modern":
            main_font = "Helvetica"
            bold_font = "Helvetica-Bold"
            accent_color = colors.HexColor("#1E3A8A")  # Deep ATS Navy
            bar_color = colors.HexColor("#3B82F6")     # Subtle Blue
        else:
            # Jake's Resume Standard (Tech standard)
            main_font = "Helvetica"
            bold_font = "Helvetica-Bold"
            accent_color = colors.HexColor("#0F172A")  # Dark slate
            bar_color = colors.HexColor("#CBD5E1")

        name_style = ParagraphStyle(
            "ATS_Name",
            parent=styles["Normal"],
            fontName=bold_font,
            fontSize=name_size,
            leading=name_leading,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=2
        )

        contact_style = ParagraphStyle(
            "ATS_Contact",
            parent=styles["Normal"],
            fontName=main_font,
            fontSize=body_size - 0.5,
            leading=body_leading,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#334155"),
            spaceAfter=5
        )

        section_style = ParagraphStyle(
            "ATS_Section",
            parent=styles["Normal"],
            fontName=bold_font,
            fontSize=sec_size,
            leading=sec_leading,
            alignment=TA_LEFT,
            textColor=accent_color,
            spaceBefore=sec_space_before,
            spaceAfter=sec_space_after,
            keepWithNext=True
        )

        subhead_style = ParagraphStyle(
            "ATS_Subhead",
            parent=styles["Normal"],
            fontName=bold_font,
            fontSize=body_size + 0.5,
            leading=body_leading,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=3,
            spaceAfter=1,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            "ATS_Body",
            parent=styles["Normal"],
            fontName=main_font,
            fontSize=body_size,
            leading=body_leading,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=1,
            spaceAfter=2
        )

        bullet_style = ParagraphStyle(
            "ATS_Bullet",
            parent=styles["Normal"],
            fontName=main_font,
            fontSize=body_size,
            leading=body_leading,
            leftIndent=12,
            firstLineIndent=-8,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=0.5,
            spaceAfter=bullet_space
        )

        story = []
        lines = markdown_text.split("\n")

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Heading 1: Name
            if line.startswith("# "):
                name_text = self._escape_for_pdf(line[2:].strip())
                story.append(Paragraph(name_text, name_style))

            # Heading 2: Section Header
            elif line.startswith("## "):
                sec_text = self._escape_for_pdf(line[3:].strip()).upper()
                story.append(Paragraph(sec_text, section_style))
                story.append(HRFlowable(width="100%", thickness=0.75, color=bar_color, spaceBefore=1, spaceAfter=3))

            # Heading 3: Role / Company / Dates
            elif line.startswith("### "):
                role_text = self._md_to_xml(line[4:].strip())
                story.append(Paragraph(role_text, subhead_style))

            # Bullet points
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = "&bull;&nbsp; " + self._md_to_xml(line[2:].strip())
                story.append(Paragraph(bullet_text, bullet_style))

            # Regular paragraph (Summary, Contact info)
            else:
                if "|" in line and ("@" in line or "linkedin" in line.lower() or "phone" in line.lower()):
                    contact_xml = self._md_to_xml(line)
                    story.append(Paragraph(contact_xml, contact_style))
                else:
                    body_xml = self._md_to_xml(line)
                    story.append(Paragraph(body_xml, body_style))

        doc.build(story)
        return output_path

    def _md_to_xml(self, text: str) -> str:
        escaped = self._escape_for_pdf(text)
        bold_converted = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)
        italic_converted = re.sub(r"\*(.*?)\*", r"<i>\1</i>", bold_converted)
        return italic_converted

    def _escape_for_pdf(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _format_bold_spans(self, paragraph, text: str):
        parts = re.split(r"(\*\*.*?\*\*)", text)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                bold_content = part[2:-2]
                run = paragraph.add_run(bold_content)
                run.bold = True
            else:
                subparts = re.split(r"(\*.*?\*)", part)
                for sp in subparts:
                    if sp.startswith("*") and sp.endswith("*") and len(sp) > 2:
                        run = paragraph.add_run(sp[1:-1])
                        run.italic = True
                    else:
                        paragraph.add_run(sp)

    def _add_bottom_border(self, paragraph):
        pPr = paragraph._element.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '2')
        bottom.set(qn('w:color'), 'CBD5E1')
        pBdr.append(bottom)
        pPr.append(pBdr)
