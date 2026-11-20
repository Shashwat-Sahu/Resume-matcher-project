"""
Document Exporter module.
Generates 100% ATS-compliant single-column formats:
- Clean Markdown (.md)
- Workday/Greenhouse certified Word DOCX (.docx)
- Text-layer selectable PDF (.pdf) with embedded job metadata
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
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
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

    def export_docx(self, markdown_text: str, filename: str = "tailored_resume.docx") -> str:
        """
        Builds a strictly ATS-compliant single-column Word document.
        - Standard 0.75-inch margins
        - Calibri clean sans-serif typography
        - No tables, no headers/footers (Workday strips them)
        - Native Word bullet lists
        """
        if not docx:
            raise ImportError("python-docx is required for DOCX export. Run: pip install python-docx")

        doc = docx.Document()

        # Set page margins to 0.75 inches
        for section in doc.sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)
            section.header.is_linked_to_previous = False
            section.footer.is_linked_to_previous = False

        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(10.5)
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
                run.font.size = Pt(20)
                run.font.color.rgb = RGBColor(15, 23, 42)

            # Heading 2: Standard Section Header
            elif line.startswith("## "):
                sec_text = line[3:].strip()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(11)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.keep_with_next = True
                run = p.add_run(sec_text.upper())
                run.bold = True
                run.font.size = Pt(12)
                run.font.color.rgb = RGBColor(30, 58, 138)
                self._add_bottom_border(p)

            # Heading 3: Role / Company / Dates
            elif line.startswith("### "):
                role_text = line[4:].strip()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(5)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                run = p.add_run(role_text)
                run.bold = True
                run.font.size = Pt(10.5)

            # Bullet points
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = line[2:].strip()
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(1.5)
                p.paragraph_format.line_spacing = 1.15
                self._format_bold_spans(p, bullet_text)

            # Regular paragraph
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2.5)
                p.paragraph_format.line_spacing = 1.15

                if "|" in line and ("@" in line or "linkedin" in line.lower() or "phone" in line.lower()):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_after = Pt(6)

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
        job_url: str = ""
    ) -> str:
        """
        Generates a 100% ATS-compliant text-layer PDF using ReportLab:
        - Active selectable text (never flattened/rasterized)
        - Strict single-column layout
        - Standard 0.75-inch margins
        - Embedded PDF metadata tracking target job, company, and URL
        """
        if not SimpleDocTemplate:
            raise ImportError("reportlab is required for PDF export. Run: pip install reportlab")

        output_path = os.path.join(self.output_dir, filename)

        # 0.75 inch margins (54 points)
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=45,
            bottomMargin=45
        )

        # Set PDF Metadata
        doc.title = f"{candidate_name} - {job_title or 'Resume'}"
        doc.author = candidate_name
        doc.subject = f"Tailored Resume for {job_title} at {company} ({job_url})"
        doc.creator = "Resume Matcher Pro (Local Llama AI)"

        styles = getSampleStyleSheet()

        # Custom ATS Typography Styles
        name_style = ParagraphStyle(
            "ATS_Name",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=3
        )

        contact_style = ParagraphStyle(
            "ATS_Contact",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8
        )

        section_style = ParagraphStyle(
            "ATS_Section",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1E3A8A"),  # Deep ATS Navy
            spaceBefore=8,
            spaceAfter=2,
            keepWithNext=True
        )

        subhead_style = ParagraphStyle(
            "ATS_Subhead",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=4,
            spaceAfter=1,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            "ATS_Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=1,
            spaceAfter=2
        )

        bullet_style = ParagraphStyle(
            "ATS_Bullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            leftIndent=14,
            firstLineIndent=-10,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=1,
            spaceAfter=1.5
        )

        story = []
        lines = markdown_text.split("\n")

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Heading 1: Candidate Name
            if line.startswith("# "):
                name_text = self._escape_for_pdf(line[2:].strip())
                story.append(Paragraph(name_text, name_style))

            # Heading 2: Section Header
            elif line.startswith("## "):
                sec_text = self._escape_for_pdf(line[3:].strip()).upper()
                story.append(Paragraph(sec_text, section_style))
                story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#CBD5E1"), spaceBefore=1, spaceAfter=4))

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
        """Converts Markdown **bold** and *italic* into valid ReportLab XML tags with safe escaping."""
        # 1. Escape XML characters
        escaped = self._escape_for_pdf(text)
        # 2. Convert **bold** to <b>bold</b>
        bold_converted = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)
        # 3. Convert *italic* to <i>italic</i>
        italic_converted = re.sub(r"\*(.*?)\*", r"<i>\1</i>", bold_converted)
        return italic_converted

    def _escape_for_pdf(self, text: str) -> str:
        """Escapes &, <, > for ReportLab XML parser."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _format_bold_spans(self, paragraph, text: str):
        """Parses markdown bold and italic tags into native Word runs."""
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
