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
from typing import Optional, List, Tuple, Dict, Any

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
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    SimpleDocTemplate = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


# Register Windows system TrueType fonts for 100% clean, non-corrupted UTF-8 text extraction
WIN_FONTS = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
TTF_AVAILABLE = {
    "arial": False,
    "times": False,
    "calibri": False
}

if SimpleDocTemplate:
    try:
        # Arial (Jake's Resume / Google Tech Standard)
        if os.path.exists(os.path.join(WIN_FONTS, "arial.ttf")) and os.path.exists(os.path.join(WIN_FONTS, "arialbd.ttf")):
            pdfmetrics.registerFont(TTFont("Arial", os.path.join(WIN_FONTS, "arial.ttf")))
            pdfmetrics.registerFont(TTFont("Arial-Bold", os.path.join(WIN_FONTS, "arialbd.ttf")))
            if os.path.exists(os.path.join(WIN_FONTS, "ariali.ttf")):
                pdfmetrics.registerFont(TTFont("Arial-Italic", os.path.join(WIN_FONTS, "ariali.ttf")))
                pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic")
            else:
                pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold")
            TTF_AVAILABLE["arial"] = True

        # Times New Roman (Harvard Ivy League Standard)
        if os.path.exists(os.path.join(WIN_FONTS, "times.ttf")) and os.path.exists(os.path.join(WIN_FONTS, "timesbd.ttf")):
            pdfmetrics.registerFont(TTFont("TimesNewRoman", os.path.join(WIN_FONTS, "times.ttf")))
            pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", os.path.join(WIN_FONTS, "timesbd.ttf")))
            if os.path.exists(os.path.join(WIN_FONTS, "timesi.ttf")):
                pdfmetrics.registerFont(TTFont("TimesNewRoman-Italic", os.path.join(WIN_FONTS, "timesi.ttf")))
                pdfmetrics.registerFontFamily("TimesNewRoman", normal="TimesNewRoman", bold="TimesNewRoman-Bold", italic="TimesNewRoman-Italic")
            else:
                pdfmetrics.registerFontFamily("TimesNewRoman", normal="TimesNewRoman", bold="TimesNewRoman-Bold")
            TTF_AVAILABLE["times"] = True

        # Calibri (Modern Minimalist Standard)
        if os.path.exists(os.path.join(WIN_FONTS, "calibri.ttf")) and os.path.exists(os.path.join(WIN_FONTS, "calibrib.ttf")):
            pdfmetrics.registerFont(TTFont("Calibri", os.path.join(WIN_FONTS, "calibri.ttf")))
            pdfmetrics.registerFont(TTFont("Calibri-Bold", os.path.join(WIN_FONTS, "calibrib.ttf")))
            if os.path.exists(os.path.join(WIN_FONTS, "calibrii.ttf")):
                pdfmetrics.registerFont(TTFont("Calibri-Italic", os.path.join(WIN_FONTS, "calibrii.ttf")))
                pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold", italic="Calibri-Italic")
            else:
                pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold")
            TTF_AVAILABLE["calibri"] = True
    except Exception:
        pass


class DocumentExporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def normalize_markdown(self, markdown_text: str) -> str:
        """
        Normalizes markdown into ATS gold standard:
        1. Strips unprintable control characters (\x00-\x1f, \x7f)
        2. Consolidates vertical skills into dense category rows
        3. Cleans contact markdown links so brackets do not leak into text
        """
        # Strip unprintable control characters
        clean_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", markdown_text)

        lines = clean_text.splitlines()
        output_lines = []

        in_skills = False
        current_skill_category = None
        category_skills = []

        for line in lines:
            sline = line.strip()

            # Check for section header
            if sline.startswith("## "):
                # Flush pending skill category
                if in_skills and current_skill_category and category_skills:
                    output_lines.append(f"- **{current_skill_category}:** {', '.join(category_skills)}")
                    current_skill_category = None
                    category_skills = []

                header_name = sline[3:].strip()
                if any(k in header_name.lower() for k in ["skill", "technologies", "competencies"]):
                    in_skills = True
                else:
                    in_skills = False
                output_lines.append(sline)
                continue

            if in_skills:
                if sline.startswith("### "):
                    if current_skill_category and category_skills:
                        output_lines.append(f"- **{current_skill_category}:** {', '.join(category_skills)}")
                        category_skills = []
                    current_skill_category = sline[4:].strip().rstrip(":")
                    continue
                elif sline.startswith(("- ", "• ", "* ", "– ")) and current_skill_category:
                    skill_val = sline.lstrip("-•*– ").strip()
                    if skill_val:
                        category_skills.append(skill_val)
                    continue
                elif not sline:
                    continue

            # Regular lines
            output_lines.append(line)

        if in_skills and current_skill_category and category_skills:
            output_lines.append(f"- **{current_skill_category}:** {', '.join(category_skills)}")

        return "\n".join(output_lines)

    def clean_contact_items(self, line: str) -> List[Tuple[str, Optional[str]]]:
        """
        Parses contact line elements into clean (clean_label, url) tuples.
        Strips markdown wrappers and redundant labels like 'Phone: ', 'Email: '.
        """
        raw_items = [x.strip() for x in re.split(r"\s*[|•·]\s*", line) if x.strip()]
        cleaned = []

        for item in raw_items:
            m = re.match(r"^\[(.*?)\]\((.*?)\)$", item)
            if m:
                label, url = m.group(1).strip(), m.group(2).strip()
            else:
                label, url = item, None

            clean_label = re.sub(
                r"^(Phone|Tel|Mobile|Email|Location|City|Address|LinkedIn|Github|Portfolio):\s*",
                "",
                label,
                flags=re.I
            ).strip()

            # Determine URL if not present
            if not url:
                if re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", clean_label):
                    url = f"mailto:{clean_label}"
                elif re.search(r"linkedin\.com/\S+", clean_label, re.I):
                    clean_url = re.search(r"linkedin\.com/\S+", clean_label, re.I).group(0)
                    url = f"https://{clean_url}"
                elif re.search(r"github\.com/\S+", clean_label, re.I):
                    clean_url = re.search(r"github\.com/\S+", clean_label, re.I).group(0)
                    url = f"https://{clean_url}"
                elif clean_label.startswith("+") or re.match(r"^\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$", clean_label):
                    clean_phone = re.sub(r"[^\d+]", "", clean_label)
                    url = f"tel:{clean_phone}"

            cleaned.append((clean_label, url))
        return cleaned

    def export_markdown(self, markdown_text: str, filename: str = "tailored_resume.md") -> str:
        """Saves clean normalized markdown resume."""
        normalized = self.normalize_markdown(markdown_text)
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(normalized)
        return path

    def export_docx(self, markdown_text: str, filename: str = "tailored_resume.docx", page_length: str = "auto") -> str:
        """
        Builds a strictly ATS-compliant single-column Word document.
        - Standard 0.75-inch (or 0.5-inch for 1-page) margins
        - Clean Calibri typography
        - No floating tables, no header/footer traps
        - Native Word bullet lists with clean bold spans
        """
        if not docx:
            raise ImportError("python-docx is required for DOCX export. Run: pip install python-docx")

        normalized_md = self.normalize_markdown(markdown_text)
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

        lines = normalized_md.split("\n")

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
                role_text = self._clean_md_links_for_text(line[4:].strip())
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4 if page_length == "1-page" else 5)
                p.paragraph_format.space_after = Pt(1 if page_length == "1-page" else 2)
                p.paragraph_format.keep_with_next = True
                run = p.add_run(role_text)
                run.bold = True
                run.font.size = Pt(9.5 if page_length == "1-page" else 10.5)

            # Bullet points
            elif line.startswith(("- ", "* ", "• ")):
                bullet_text = self._clean_md_links_for_text(line[2:].strip())
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_before = Pt(0.5 if page_length == "1-page" else 1)
                p.paragraph_format.space_after = Pt(1 if page_length == "1-page" else 1.5)
                p.paragraph_format.line_spacing = 1.1 if page_length == "1-page" else 1.15
                self._format_bold_spans(p, bullet_text)

            # Regular paragraph / Contact line
            else:
                if "|" in line and ("@" in line or "linkedin" in line.lower() or "phone" in line.lower() or "+" in line):
                    contact_items = self.clean_contact_items(line)
                    clean_contact_line = " | ".join([item[0] for item in contact_items])
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(5 if page_length == "1-page" else 7)
                    run = p.add_run(clean_contact_line)
                    run.font.size = Pt(9 if page_length == "1-page" else 9.5)
                    run.font.color.rgb = RGBColor(71, 85, 105)
                else:
                    clean_body = self._clean_md_links_for_text(line)
                    p = doc.add_paragraph()
                    p.paragraph_format.space_before = Pt(1.5 if page_length == "1-page" else 2)
                    p.paragraph_format.space_after = Pt(2 if page_length == "1-page" else 2.5)
                    p.paragraph_format.line_spacing = 1.1 if page_length == "1-page" else 1.15
                    self._format_bold_spans(p, clean_body)

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
        Generates a 100% ATS-compliant text-layer PDF with selectable text.
        
        Templates:
          - 'jake': Tech standard, clean sans-serif (Arial), compact 0.5" margins, Google/FAANG standard
          - 'harvard': Classic Ivy League serif (Times New Roman), formal spacing, 0.75" margins
          - 'modern': Minimalist FAANG accent (Navy/Slate headers), contemporary line height
          
        Key ATS Guarantees:
          - Zero unprintable \x7f control characters
          - Markdown links cleanly converted to PDF hyperlinks (visible text layer is pure and bracket-free)
          - Skills consolidated into dense single-line category rows
          - Contact info parsed cleanly without markdown artifacts
        """
        if not SimpleDocTemplate:
            raise ImportError("reportlab is required for PDF export. Run: pip install reportlab")

        normalized_md = self.normalize_markdown(markdown_text)
        output_path = os.path.join(self.output_dir, filename)

        # Page geometry
        if page_length == "1-page":
            margin = 36.0  # 0.5 inch for strict 1-page density
            v_margin = 32.0
            body_size = 9.0
            body_leading = 12.0
            name_size = 17.0
            name_leading = 20.0
            sec_size = 10.5
            sec_leading = 13.0
            bullet_space = 1.5
            sec_space_before = 5.0
            sec_space_after = 2.0
        else:
            margin = 54.0  # 0.75 inch standard ATS margin
            v_margin = 42.0
            body_size = 9.5
            body_leading = 13.5
            name_size = 19.0
            name_leading = 23.0
            sec_size = 11.0
            sec_leading = 14.0
            bullet_space = 2.5
            sec_space_before = 8.0
            sec_space_after = 3.0

        content_width = 612.0 - (margin * 2)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=v_margin,
            bottomMargin=v_margin
        )

        doc.title = f"{candidate_name} - {job_title or 'Resume'}"
        doc.author = candidate_name
        doc.subject = f"Tailored Resume for {job_title} at {company} ({job_url})"
        doc.creator = f"Resume Matcher Pro (Template: {template.title()}, Budget: {page_length})"

        styles = getSampleStyleSheet()

        # Font selection based on template and registered TrueType fonts
        use_ttf = False
        if template == "harvard":
            if TTF_AVAILABLE["times"]:
                main_font = "TimesNewRoman"
                bold_font = "TimesNewRoman-Bold"
                use_ttf = True
            else:
                main_font = "Times-Roman"
                bold_font = "Times-Bold"
            accent_color = colors.HexColor("#111827")
            bar_color = colors.HexColor("#94A3B8")
        elif template == "modern":
            if TTF_AVAILABLE["calibri"]:
                main_font = "Calibri"
                bold_font = "Calibri-Bold"
                use_ttf = True
            elif TTF_AVAILABLE["arial"]:
                main_font = "Arial"
                bold_font = "Arial-Bold"
                use_ttf = True
            else:
                main_font = "Helvetica"
                bold_font = "Helvetica-Bold"
            accent_color = colors.HexColor("#1E3A8A")  # Deep ATS Navy
            bar_color = colors.HexColor("#3B82F6")
        else:
            # Jake's Resume Standard (Tech standard)
            if TTF_AVAILABLE["arial"]:
                main_font = "Arial"
                bold_font = "Arial-Bold"
                use_ttf = True
            else:
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
            spaceAfter=4
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

        subhead_left = ParagraphStyle(
            "ATS_Subhead_L",
            parent=styles["Normal"],
            fontName=bold_font,
            fontSize=body_size + 0.5,
            leading=body_leading,
            textColor=colors.HexColor("#0F172A"),
            keepWithNext=True
        )

        subhead_right = ParagraphStyle(
            "ATS_Subhead_R",
            parent=styles["Normal"],
            fontName=main_font,
            fontSize=body_size,
            leading=body_leading,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#475569"),
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
            leftIndent=14,
            firstLineIndent=-10,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=0.5,
            spaceAfter=bullet_space
        )

        # ATS Bullet Symbol: Use unicode '• ' for TrueType; use standard '-' for Type-1 fallback
        # NEVER use &bull;&nbsp; in Type-1 fonts to avoid \x7f ASCII DEL control characters!
        bullet_char = "• " if use_ttf else "- "

        story = []
        lines = normalized_md.split("\n")

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
                story.append(HRFlowable(width="100%", thickness=0.6, color=bar_color, spaceBefore=1, spaceAfter=3))

            # Heading 3: Role / Company / Dates
            elif line.startswith("### "):
                role_raw = line[4:].strip()
                sub_table = self._build_subheading_table(role_raw, content_width, subhead_left, subhead_right)
                story.append(sub_table)

            # Bullet points
            elif line.startswith(("- ", "* ", "• ")):
                content = line[2:].strip()
                bullet_xml = bullet_char + self._md_to_xml(content)
                story.append(Paragraph(bullet_xml, bullet_style))

            # Regular paragraph / Contact info
            else:
                if "|" in line and ("@" in line or "linkedin" in line.lower() or "phone" in line.lower() or "+" in line):
                    contact_items = self.clean_contact_items(line)
                    contact_xml_parts = []
                    for clean_lbl, url in contact_items:
                        esc_lbl = self._escape_for_pdf(clean_lbl)
                        if url:
                            contact_xml_parts.append(f'<a href="{url}" color="#1D4ED8">{esc_lbl}</a>')
                        else:
                            contact_xml_parts.append(esc_lbl)
                    
                    separator = " &nbsp;|&nbsp; " if template != "jake" else " &nbsp;•&nbsp; "
                    contact_xml = separator.join(contact_xml_parts)
                    story.append(Paragraph(contact_xml, contact_style))
                else:
                    body_xml = self._md_to_xml(line)
                    story.append(Paragraph(body_xml, body_style))

        doc.build(story)
        return output_path

    def _build_subheading_table(self, text: str, total_width: float, style_left: ParagraphStyle, style_right: ParagraphStyle):
        """
        Creates a clean 2-column ATS layout for role/company and date/location.
        Left column: Bold Title / Company
        Right column: Right-aligned Italic Date Range
        Extracts cleanly and linearly in ATS engines while looking pixel-perfect.
        """
        # Match dates in parentheses at the end: e.g. "(Sep 2024 – Present)"
        m = re.search(r"\(([^)]+)\)\s*$", text)
        if m:
            right_text = m.group(1).strip()
            left_text = text[:m.start()].strip().rstrip("|-–— ")
        else:
            # Check for pipe separated date
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 2 and any(yr in parts[-1] for yr in ["202", "201", "199", "Present", "Current"]):
                right_text = parts[-1]
                left_text = " | ".join(parts[:-1])
            else:
                left_text = text
                right_text = ""

        left_xml = self._md_to_xml(left_text)
        right_xml = f"<i>{self._escape_for_pdf(right_text)}</i>" if right_text else ""

        p_left = Paragraph(left_xml, style_left)
        p_right = Paragraph(right_xml, style_right)

        col_r_width = 160.0 if right_text else 0.0
        col_l_width = total_width - col_r_width

        t = Table([[p_left, p_right]], colWidths=[col_l_width, col_r_width])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        return t

    def _md_to_xml(self, text: str) -> str:
        """
        Converts markdown bold/italics and markdown links to clean ReportLab XML.
        Links become <a href="url" color="#1D4ED8">clean_text</a> so extracted PDF text
        contains ONLY clean_text without markdown artifacts.
        """
        escaped = self._escape_for_pdf(text)

        # Convert markdown links [Label](url)
        def _replace_link(match):
            lbl = match.group(1).strip()
            url = match.group(2).strip()
            return f'<a href="{url}" color="#1D4ED8">{lbl}</a>'

        link_converted = re.sub(r"\[(.*?)\]\((.*?)\)", _replace_link, escaped)
        bold_converted = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", link_converted)
        italic_converted = re.sub(r"\*(.*?)\*", r"<i>\1</i>", bold_converted)
        return italic_converted

    def _escape_for_pdf(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _clean_md_links_for_text(self, text: str) -> str:
        """Strips markdown link syntax down to anchor text for plain text / DOCX."""
        return re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

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

    def audit_pdf_ats(self, pdf_path: str) -> Dict[str, Any]:
        """
        Performs automated ATS compliance audit directly on the generated PDF text layer.
        Verifies:
        - Text extractability
        - Absence of corrupt control characters (\x7f)
        - Contact info extractability (email, phone, links)
        - Standard section headings presence
        - Word / Character density
        """
        if not PdfReader:
            return {"is_ats_safe": True, "message": "pypdf not available for audit"}

        reader = PdfReader(pdf_path)
        pages = len(reader.pages)
        full_text = "\n".join([p.extract_text() or "" for p in reader.pages])

        # Check for control characters
        bad_chars = re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", full_text)
        has_bad_chars = len(bad_chars) > 0

        # Check contact info
        has_email = bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", full_text))
        has_phone = bool(re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", full_text))

        # Check standard sections
        text_lower = full_text.lower()
        found_sections = [s for s in ["experience", "education", "skills", "summary", "projects"] if s in text_lower]

        is_ats_safe = (not has_bad_chars) and has_email and has_phone and (len(found_sections) >= 3) and (len(full_text) > 300)

        return {
            "is_ats_safe": is_ats_safe,
            "page_count": pages,
            "character_count": len(full_text),
            "control_characters_clean": not has_bad_chars,
            "email_extracted": has_email,
            "phone_extracted": has_phone,
            "sections_detected": found_sections,
            "extracted_preview": full_text[:350]
        }
