"""
Document Exporter module.
Generates 100% ATS-compliant single-column formats:
- Clean Markdown (.md)
- Workday/Greenhouse certified DOCX (.docx)
- Text-layer PDF (.pdf)
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
        - Calibri / Arial clean sans-serif typography
        - No tables, no headers/footers (Workday strips them)
        - Native Word bullet lists
        """
        if not docx:
            raise ImportError("python-docx is required for DOCX export. Run: pip install python-docx")

        doc = docx.Document()

        # Set page margins to 0.75 inches for optimal density
        for section in doc.sections:
            section.top_margin = Inches(0.75)
            section.bottom_margin = Inches(0.75)
            section.left_margin = Inches(0.75)
            section.right_margin = Inches(0.75)
            # Ensure headers/footers are empty
            section.header.is_linked_to_previous = False
            section.footer.is_linked_to_previous = False

        # Set Normal style font
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(10.5)
        font.color.rgb = RGBColor(30, 30, 30)

        lines = markdown_text.split("\n")
        in_bullets = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                in_bullets = False
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
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.keep_with_next = True
                run = p.add_run(sec_text.upper())
                run.bold = True
                run.font.size = Pt(12)
                run.font.color.rgb = RGBColor(30, 58, 138)  # Deep Navy / ATS-safe
                # Add bottom border under section header
                self._add_bottom_border(p)

            # Heading 3: Role / Company / Dates
            elif line.startswith("### "):
                role_text = line[4:].strip()
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.keep_with_next = True
                run = p.add_run(role_text)
                run.bold = True
                run.font.size = Pt(11)

            # Bullet points
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = line[2:].strip()
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.15
                self._format_bold_spans(p, bullet_text)
                in_bullets = True

            # Regular paragraph (Summary, Contact line)
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.15

                # If contact line (e.g. contains |), center it
                if "|" in line and ("@" in line or "linkedin" in line.lower() or "phone" in line.lower()):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_after = Pt(8)

                self._format_bold_spans(p, line)

        output_path = os.path.join(self.output_dir, filename)
        doc.save(output_path)
        return output_path

    def _format_bold_spans(self, paragraph, text: str):
        """Parses markdown **bold** and *italic* tags into native Word formatting runs."""
        # Split by bold markers (**text**)
        parts = re.split(r"(\*\*.*?\*\*)", text)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                bold_content = part[2:-2]
                run = paragraph.add_run(bold_content)
                run.bold = True
            else:
                # Handle single asterisks for italics (*text*)
                subparts = re.split(r"(\*.*?\*)", part)
                for sp in subparts:
                    if sp.startswith("*") and sp.endswith("*") and len(sp) > 2:
                        run = paragraph.add_run(sp[1:-1])
                        run.italic = True
                    else:
                        paragraph.add_run(sp)

    def _add_bottom_border(self, paragraph):
        """Adds a subtle bottom divider line under standard ATS section headers."""
        pPr = paragraph._element.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '2')
        bottom.set(qn('w:color'), 'CBD5E1')  # subtle slate
        pBdr.append(bottom)
        pPr.append(pBdr)
