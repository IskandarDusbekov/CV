"""
Word (.docx) eksport.

Har bir veb-shablonning ranglari, shriftlari va joylashuvi Word'da tahrirlashga qulay
shaklda takrorlanadi: yon panelli shablonlar — ikki ustunli jadval (panel katagi bo'yalgan),
bir ustunli shablonlar — oddiy paragraflar. Matn oddiy, tahrirlanadigan holda qoladi.
"""
from dataclasses import dataclass
from io import BytesIO

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from apps.core.models import SiteSettings

from .services import build_cv_context


@dataclass(frozen=True)
class Theme:
    layout: str              # "sidebar" | "header_split" | "banner" | "single_center" | "single_labels"
    body_font: str
    heading_font: str
    text: str
    muted: str
    accent: str
    rule: str
    side_bg: str = "FFFFFF"
    side_text: str = "1F2937"
    side_muted: str = "6B7280"
    side_accent: str = ""
    banner_bg: str = ""
    name_color: str = ""
    uppercase_headings: bool = True


THEMES = {
    "ats": Theme("single_ats", "Arial", "Arial", "111111", "444444", "111111", "111111"),
    "ats_modern": Theme("single_ats", "Calibri", "Calibri", "111827", "4B5563", "1E3A8A", "1E3A8A"),
    "classic": Theme("sidebar", "Calibri", "Calibri", "1F2937", "4B5563", "1E2A44", "D6DCE5",
                     side_bg="1E2A44", side_text="FFFFFF", side_muted="B8C2D6", side_accent="8FB3FF"),
    "modern": Theme("header_split", "Calibri", "Calibri", "0F172A", "475569", "0D9488", "E2E8F0",
                    side_bg="F1F5F9", side_text="0F172A", side_muted="475569", side_accent="0D9488"),
    "creative": Theme("banner", "Calibri", "Calibri", "1E1B2E", "5B5670", "7C3AED", "EDE4FB",
                      side_bg="F7F2FF", side_text="1E1B2E", side_muted="5B5670", side_accent="7C3AED",
                      banner_bg="6D28D9"),
    "executive": Theme("single_center", "Georgia", "Georgia", "1C1917", "57534E", "A07B45", "D9CBB5",
                       name_color="1C1917"),
    "minimal": Theme("single_labels", "Arial", "Arial", "111111", "6B7280", "111111", "E5E7EB"),
    "dark": Theme("sidebar", "Calibri", "Consolas", "111827", "4B5563", "B7791F", "E5E7EB",
                  side_bg="12161C", side_text="E6E8EB", side_muted="9AA3AE", side_accent="F5B301"),
    "elegant": Theme("sidebar", "Calibri", "Georgia", "2B2520", "6B6158", "8B6F4E", "E6DCCD",
                     side_bg="F3EDE3", side_text="2B2520", side_muted="6B6158", side_accent="8B6F4E",
                     uppercase_headings=False),
}


# ─── Low-level helpers ────────────────────────────────────────────────────────

def _rgb(hex_color):
    return RGBColor.from_string(hex_color.upper())


def _shade(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _cell_margins(cell, top=0, bottom=0, left=0, right=0):
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for side, value in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(int(value)))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tc_pr.append(mar)


def _no_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "nil")
        borders.append(node)
    tbl_pr.append(borders)


def _fixed_widths(table, widths_cm):
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    for row in table.rows:
        for cell, width in zip(row.cells, widths_cm):
            cell.width = Cm(width)


def _bottom_rule(paragraph, hex_color, size=6):
    p_pr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), hex_color)
    borders.append(bottom)
    p_pr.append(borders)


def _spacing(paragraph, before=0, after=0, line=1.15):
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line


def _run(paragraph, text, *, font, size, color, bold=False, italic=False, caps=False, spacing=0):
    run = paragraph.add_run(text)
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.font.color.rgb = _rgb(color)
    run.font.bold = bold
    run.font.italic = italic
    run.font.all_caps = caps
    if spacing:
        r_pr = run._element.get_or_add_rPr()
        sp = OxmlElement("w:spacing")
        sp.set(qn("w:val"), str(spacing))
        r_pr.append(sp)
    return run


class Writer:
    """Paragraflarni hujjat yoki jadval katagiga yozadi, shablon ranglarini hisobga olib."""

    def __init__(self, container, theme, *, on_side=False):
        self.c = container
        self.t = theme
        self.on_side = on_side
        self._fresh_cell = hasattr(container, "_tc")

    @property
    def text_color(self):
        return self.t.side_text if self.on_side else self.t.text

    @property
    def muted_color(self):
        return self.t.side_muted if self.on_side else self.t.muted

    @property
    def accent_color(self):
        return (self.t.side_accent or self.t.accent) if self.on_side else self.t.accent

    def par(self, align=None, before=0, after=2, style=None):
        if self._fresh_cell and self.c.paragraphs and not self.c.paragraphs[0].runs:
            p = self.c.paragraphs[0]
            self._fresh_cell = False
            if style:
                p.style = style
        else:
            p = self.c.add_paragraph(style=style) if style else self.c.add_paragraph()
        _spacing(p, before, after)
        if align is not None:
            p.alignment = align
        return p

    def text(self, value, *, size=10, bold=False, italic=False, muted=False, accent=False,
             align=None, before=0, after=2, font=None):
        p = self.par(align, before, after)
        color = self.accent_color if accent else self.muted_color if muted else self.text_color
        _run(p, value, font=font or self.t.body_font, size=size, color=color, bold=bold, italic=italic)
        return p

    def heading(self, value, *, align=None, rule=True, size=10.5):
        p = self.par(align, before=12, after=5)
        _run(p, value, font=self.t.heading_font, size=size, color=self.accent_color, bold=True,
             caps=self.t.uppercase_headings, spacing=20 if self.t.uppercase_headings else 0)
        if rule and not self.on_side:
            _bottom_rule(p, self.t.rule)
        return p

    def bullet(self, value, size=9.5):
        p = self.par(before=0, after=1.5, style="List Bullet")
        _run(p, value, font=self.t.body_font, size=size, color=self.text_color)
        return p

    def pair(self, left, right, *, size=10.5):
        """Lavozim (qalin) va sana (o'ngda, xira) bitta qatorda — tab to'xtash nuqtasi bilan."""
        p = self.par(before=6, after=0)
        _run(p, left, font=self.t.body_font, size=size, color=self.text_color, bold=True)
        if right:
            _run(p, "\t" + right, font=self.t.body_font, size=size - 1.5, color=self.muted_color)
            width = self._available_width()
            p.paragraph_format.tab_stops.add_tab_stop(width, alignment=2)  # RIGHT
        return p

    def _available_width(self):
        if hasattr(self.c, "width") and self.c.width:
            return self.c.width - Cm(0.9)
        section = self.c.sections[-1]
        return section.page_width - section.left_margin - section.right_margin


# ─── Content blocks ───────────────────────────────────────────────────────────

def _contact_lines(data):
    return [i["value"] for i in data["contact_items"]] + [i["value"] for i in data["profile_links"]]


def _write_main(w, data):
    labels = data["labels"]
    if data["summary"]:
        w.heading(labels["profile_summary"])
        w.text(data["summary"], size=10, after=2)

    if data["experience"]:
        w.heading(labels["experience"])
        for exp in data["experience"]:
            w.pair(exp["position"] or labels["position"], exp["duration"])
            if exp["company"]:
                w.text(exp["company"], size=9.5, accent=True, bold=True, after=2)
            for item in exp["responsibilities"]:
                w.bullet(item)

    if data["projects"]:
        w.heading(labels["projects"])
        for proj in data["projects"]:
            w.text(proj["title"] or labels["project"], size=10.5, bold=True, before=5, after=1)
            if proj["description"]:
                w.text(proj["description"], size=9.5, after=1)
            if proj["technologies"]:
                w.text(" · ".join(proj["technologies"]), size=9, muted=True, after=2)


def _write_side(w, data, *, include_contact=True, include_education=True):
    labels = data["labels"]
    contacts = _contact_lines(data)
    if include_contact and contacts:
        w.heading(labels["contact"], rule=False, size=9.5)
        for line in contacts:
            w.text(line, size=9, after=2)
    if data["skills"]:
        w.heading(labels["skills"], rule=False, size=9.5)
        for skill in data["skills"]:
            w.text("•  " + skill, size=9, after=1)
    if data["languages"]:
        w.heading(labels["languages"], rule=False, size=9.5)
        for lang in data["languages"]:
            w.text(lang, size=9, after=1)
    if include_education and data["education"]:
        w.heading(labels["education"], rule=False, size=9.5)
        for edu in data["education"]:
            w.text(edu["institution"], size=9.5, bold=True, before=3, after=0)
            meta = " · ".join(filter(None, [edu["degree"], edu["year"]]))
            if meta:
                w.text(meta, size=8.5, muted=True, after=2)


def _write_photo(w, photo_path, width_cm=3.0, align=WD_ALIGN_PARAGRAPH.LEFT):
    if not photo_path:
        return
    try:
        p = w.par(align=align, after=8)
        p.add_run().add_picture(photo_path, width=Cm(width_cm))
    except Exception:
        pass


# ─── Layouts ──────────────────────────────────────────────────────────────────

def _two_column(doc, widths, side_first=True, side_bg=None):
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _no_borders(table)
    _fixed_widths(table, widths)
    cells = table.rows[0].cells
    side, main = (cells[0], cells[1]) if side_first else (cells[1], cells[0])
    for cell in cells:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    _cell_margins(side, top=420, bottom=420, left=340, right=300)
    _cell_margins(main, top=420, bottom=420, left=420, right=380)
    if side_bg:
        _shade(side, side_bg)
    return side, main


def _layout_sidebar(doc, data, theme, photo):
    side_cell, main_cell = _two_column(doc, [6.4, 13.6], side_bg=theme.side_bg)
    side = Writer(side_cell, theme, on_side=True)
    _write_photo(side, photo, 3.2)
    side.text(data["full_name"], size=17, bold=True, font=theme.heading_font, after=1)
    side.text(data["job_title"], size=10, accent=True, after=6)
    _write_side(side, data)
    _write_main(Writer(main_cell, theme), data)


def _layout_header_split(doc, data, theme, photo):
    head = Writer(doc, theme)
    top = head.par(after=0)
    _run(top, data["full_name"], font=theme.heading_font, size=26, color=theme.text, bold=True)
    head.text(data["job_title"], size=12, accent=True, bold=True, after=3)
    contacts = _contact_lines(data)
    if contacts:
        p = head.text("   |   ".join(contacts), size=9, muted=True, after=10)
        _bottom_rule(p, theme.accent, size=18)
    main_cell, side_cell = _two_column(doc, [12.6, 7.4], side_first=False, side_bg=theme.side_bg)
    _write_main(Writer(main_cell, theme), data)
    side = Writer(side_cell, theme, on_side=True)
    _write_photo(side, photo, 3.0)
    _write_side(side, data, include_contact=False)


def _layout_banner(doc, data, theme, photo):
    banner = doc.add_table(rows=1, cols=1)
    banner.alignment = WD_TABLE_ALIGNMENT.CENTER
    _no_borders(banner)
    _fixed_widths(banner, [20.0])
    cell = banner.rows[0].cells[0]
    _shade(cell, theme.banner_bg)
    _cell_margins(cell, top=480, bottom=480, left=480, right=480)
    bw = Writer(cell, Theme(**{**theme.__dict__, "text": "FFFFFF", "muted": "E9D5FF", "accent": "FFFFFF"}))
    bw.text(data["full_name"], size=26, bold=True, font=theme.heading_font, after=0)
    bw.text(data["job_title"], size=12, muted=True, after=4)
    contacts = _contact_lines(data)
    if contacts:
        bw.text("  ·  ".join(contacts), size=9, after=0)
    side_cell, main_cell = _two_column(doc, [6.6, 13.4], side_bg=theme.side_bg)
    side = Writer(side_cell, theme, on_side=True)
    _write_photo(side, photo, 3.0)
    _write_side(side, data, include_contact=False)
    _write_main(Writer(main_cell, theme), data)


def _layout_single_center(doc, data, theme, photo):
    w = Writer(doc, theme)
    center = WD_ALIGN_PARAGRAPH.CENTER
    _write_photo(w, photo, 2.8, align=center)
    w.text(data["full_name"], size=28, bold=True, font=theme.heading_font, align=center, after=0)
    p = w.text(data["job_title"].upper(), size=10.5, accent=True, align=center, after=4)
    contacts = _contact_lines(data)
    if contacts:
        p = w.text("  ·  ".join(contacts), size=9, muted=True, align=center, after=6)
    _bottom_rule(p, theme.accent, size=8)
    _write_main(w, data)
    if data["education"]:
        w.heading(data["labels"]["education"])
        for edu in data["education"]:
            w.pair(edu["institution"], edu["year"])
            if edu["degree"]:
                w.text(edu["degree"], size=9.5, muted=True, after=2)
    if data["skills"]:
        w.heading(data["labels"]["skills"])
        w.text("  ·  ".join(data["skills"]), size=10)
    if data["languages"]:
        w.heading(data["labels"]["languages"])
        w.text("  ·  ".join(data["languages"]), size=10)


def _layout_single_labels(doc, data, theme, photo):
    w = Writer(doc, theme)
    w.text(data["full_name"], size=30, bold=True, font=theme.heading_font, after=0)
    w.text(data["job_title"], size=12, muted=True, after=4)
    contacts = _contact_lines(data)
    if contacts:
        p = w.text("     ".join(contacts), size=9, after=10)
        _bottom_rule(p, "111111", size=12)

    labels = data["labels"]

    def row(label):
        table = doc.add_table(rows=1, cols=2)
        _no_borders(table)
        _fixed_widths(table, [4.0, 13.6])
        left, right = table.rows[0].cells
        _cell_margins(left, top=180, bottom=60)
        _cell_margins(right, top=180, bottom=60)
        lp = left.paragraphs[0]
        _run(lp, label, font=theme.heading_font, size=8.5, color=theme.muted, bold=True, caps=True, spacing=30)
        return Writer(right, theme)

    if data["summary"]:
        row(labels["profile_summary"]).text(data["summary"], size=10)
    if data["experience"]:
        rw = row(labels["experience"])
        for exp in data["experience"]:
            rw.pair(exp["position"] or labels["position"], exp["duration"])
            if exp["company"]:
                rw.text(exp["company"], size=9.5, muted=True, after=2)
            for item in exp["responsibilities"]:
                rw.bullet(item)
    if data["projects"]:
        rw = row(labels["projects"])
        for proj in data["projects"]:
            rw.text(proj["title"], size=10.5, bold=True, before=4, after=1)
            if proj["description"]:
                rw.text(proj["description"], size=9.5, after=1)
            if proj["technologies"]:
                rw.text(" · ".join(proj["technologies"]), size=9, muted=True)
    if data["education"]:
        rw = row(labels["education"])
        for edu in data["education"]:
            rw.pair(edu["institution"], edu["year"])
            if edu["degree"]:
                rw.text(edu["degree"], size=9.5, muted=True)
    if data["skills"]:
        row(labels["skills"]).text("  ·  ".join(data["skills"]), size=10)
    if data["languages"]:
        row(labels["languages"]).text("  ·  ".join(data["languages"]), size=10)


def _layout_single_ats(doc, data, theme, photo):
    """ATS uchun: jadval, rasm, ustun yo'q — faqat standart paragraflar va Word ro'yxatlari."""
    w = Writer(doc, theme)
    labels = data["labels"]
    center = WD_ALIGN_PARAGRAPH.CENTER if theme.accent == "111111" else None
    p = w.par(align=center, after=0)
    _run(p, data["full_name"], font=theme.heading_font, size=22, color=theme.accent, bold=True)
    w.text(data["job_title"], size=12, bold=True, align=center, after=2)
    contacts = _contact_lines(data)
    if contacts:
        p = w.text(" | ".join(contacts), size=9.5, muted=True, align=center, after=6)
        _bottom_rule(p, theme.rule, size=12)

    if data["summary"]:
        w.heading(labels["profile_summary"])
        w.text(data["summary"], size=10.5)
    sections = ["experience", "skills", "projects", "education", "languages"]
    if theme.accent == "111111":
        sections = ["skills", "experience", "projects", "education", "languages"]
    for key in sections:
        if key == "skills" and data["skills"]:
            w.heading(labels["skills"])
            w.text(", ".join(data["skills"]), size=10.5)
        elif key == "experience" and data["experience"]:
            w.heading(labels["experience"])
            for exp in data["experience"]:
                w.pair(exp["position"] or labels["position"], exp["duration"], size=11)
                if exp["company"]:
                    w.text(exp["company"], size=10.5, italic=True, muted=True, after=1)
                for item in exp["responsibilities"]:
                    w.bullet(item, size=10.5)
        elif key == "projects" and data["projects"]:
            w.heading(labels["projects"])
            for proj in data["projects"]:
                w.text(proj["title"], size=11, bold=True, before=4, after=0)
                if proj["description"]:
                    w.text(proj["description"], size=10.5, after=0)
                if proj["technologies"]:
                    w.text(", ".join(proj["technologies"]), size=10, muted=True)
        elif key == "education" and data["education"]:
            w.heading(labels["education"])
            for edu in data["education"]:
                w.pair(edu["institution"], edu["year"], size=11)
                if edu["degree"]:
                    w.text(edu["degree"], size=10.5, italic=True, muted=True)
        elif key == "languages" and data["languages"]:
            w.heading(labels["languages"])
            w.text(", ".join(data["languages"]), size=10.5)


LAYOUTS = {
    "single_ats": _layout_single_ats,
    "sidebar": _layout_sidebar,
    "header_split": _layout_header_split,
    "banner": _layout_banner,
    "single_center": _layout_single_center,
    "single_labels": _layout_single_labels,
}


def render_cv_to_docx(cv, user) -> bytes:
    context = build_cv_context(cv, user)
    data = context["cv_data"]
    theme = THEMES[context["template_key"]]

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    full_bleed = theme.layout in {"sidebar", "banner"}
    section.left_margin = section.right_margin = Cm(0.5 if full_bleed else 1.9)
    section.top_margin = section.bottom_margin = Cm(0.5 if full_bleed else 1.6)

    normal = doc.styles["Normal"]
    normal.font.name = theme.body_font
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), theme.body_font)
    normal.font.size = Pt(10)
    normal.font.color.rgb = _rgb(theme.text)

    core = doc.core_properties
    core.title = f"{data['full_name']} — CV"
    core.author = data["full_name"]
    core.comments = f"{SiteSettings.load().site_name} orqali yaratilgan"

    photo_path = ""
    if getattr(cv, "photo", None):
        try:
            photo_path = cv.photo.path
        except Exception:
            photo_path = ""

    LAYOUTS[theme.layout](doc, data, theme, photo_path)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
