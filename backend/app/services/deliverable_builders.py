"""Low-level pptx/docx building blocks for the modern-minimalist deliverable template (Phase 6).

These helpers keep the aesthetic consistent (whitespace, thin accent rule, light titles) and are the
only place that touches python-pptx / python-docx layout, so the theme can be swapped centrally.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from docx import Document
from docx.shared import Pt as DocxPt
from docx.shared import RGBColor as DocxRGB
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

from .deliverable_theme import Theme

SLIDE_W = Inches(13.333)  # 16:9
SLIDE_H = Inches(7.5)


def _rgb(hexstr: str) -> RGBColor:
    return RGBColor.from_string(hexstr)


def new_presentation() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def _blank(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])  # blank layout


def _textbox(slide, left, top, width, height, text, *, size, color, bold=False, font="Calibri"):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font
    run.font.color.rgb = _rgb(color)
    return box


def _accent_rule(slide, theme: Theme, top=Inches(1.5), left=Inches(0.9), width=Inches(2.2)):
    line = slide.shapes.add_shape(1, left, top, width, Emu(34000))  # ~thin bar
    line.fill.solid()
    line.fill.fore_color.rgb = _rgb(theme.accent)
    line.line.fill.background()


def title_slide(prs: Presentation, theme: Theme, title: str, subtitle: str) -> None:
    slide = _blank(prs)
    # Brand logo (top-left) when one is configured (D12).
    logo_path = (theme.extras or {}).get("logo_path")
    if logo_path:
        try:
            slide.shapes.add_picture(logo_path, Inches(0.9), Inches(0.7), height=Inches(0.8))
        except Exception:  # noqa: BLE001 - a bad/missing logo must never break generation
            pass
    _textbox(slide, Inches(0.9), Inches(2.6), Inches(11.5), Inches(1.6), title,
             size=40, color=theme.ink, bold=False, font=theme.title_font)
    _accent_rule(slide, theme, top=Inches(2.4))
    _textbox(slide, Inches(0.9), Inches(4.0), Inches(11.5), Inches(1.0), subtitle,
             size=16, color=theme.muted, font=theme.body_font)
    if theme.name and theme.name not in ("minimal", "brand"):
        _textbox(slide, Inches(0.9), Inches(6.7), Inches(11.5), Inches(0.5), theme.name,
                 size=11, color=theme.muted, font=theme.body_font)


def section_slide(prs: Presentation, theme: Theme, heading: str, bullets: Sequence[str]) -> None:
    slide = _blank(prs)
    _textbox(slide, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.9), heading,
             size=28, color=theme.ink, font=theme.title_font)
    _accent_rule(slide, theme, top=Inches(1.55), width=Inches(1.4))
    box = slide.shapes.add_textbox(Inches(0.9), Inches(1.9), Inches(11.5), Inches(5.0))
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = p.add_run()
        run.text = f"•  {b}"
        run.font.size = Pt(16)
        run.font.name = theme.body_font
        run.font.color.rgb = _rgb(theme.ink)
        p.space_after = Pt(10)


def metric_slide(prs: Presentation, theme: Theme, heading: str, stats: List[Tuple[str, str]]) -> None:
    """A heading + a row/grid of big-number stat cards (label, value)."""
    slide = _blank(prs)
    _textbox(slide, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.9), heading,
             size=28, color=theme.ink, font=theme.title_font)
    _accent_rule(slide, theme, top=Inches(1.55), width=Inches(1.4))
    cols = 3
    cw, ch = Inches(3.6), Inches(1.6)
    for idx, (label, value) in enumerate(stats):
        r, c = divmod(idx, cols)
        left = Inches(0.9) + c * (cw + Inches(0.3))
        top = Inches(2.1) + r * (ch + Inches(0.3))
        _textbox(slide, left, top, cw, Inches(0.5), label.upper(),
                 size=11, color=theme.muted, font=theme.body_font)
        _textbox(slide, left, top + Inches(0.4), cw, Inches(1.0), value,
                 size=30, color=theme.ink, font=theme.title_font)


def table_slide(prs: Presentation, theme: Theme, heading: str, headers: Sequence[str],
                rows: Sequence[Sequence[str]]) -> None:
    slide = _blank(prs)
    _textbox(slide, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.9), heading,
             size=28, color=theme.ink, font=theme.title_font)
    _accent_rule(slide, theme, top=Inches(1.55), width=Inches(1.4))
    n_rows = len(rows) + 1
    n_cols = len(headers)
    gt = slide.shapes.add_table(n_rows, n_cols, Inches(0.9), Inches(1.9),
                                Inches(11.5), Inches(0.4 * n_rows)).table
    for c, h in enumerate(headers):
        cell = gt.cell(0, c)
        cell.text = h
        cell.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        cell.text_frame.paragraphs[0].runs[0].font.bold = True
        cell.text_frame.paragraphs[0].runs[0].font.color.rgb = _rgb(theme.ground)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(theme.accent)
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            cell = gt.cell(r, c)
            cell.text = str(val)
            run = cell.text_frame.paragraphs[0].runs[0]
            run.font.size = Pt(11)
            run.font.color.rgb = _rgb(theme.ink)


def provenance_slide(prs: Presentation, theme: Theme, summary: dict) -> None:
    """Auto-generated provenance disclosure slide (transparency as a feature, PRD M6)."""
    bullets = [f"{k}: {v}" for k, v in (summary.get("by_source") or {}).items()]
    bullets.append(f"Client-ready items: {summary.get('client_ready', 0)} / {summary.get('total', 0)}")
    if summary.get("excluded_unreviewed_model_inferred"):
        bullets.append(
            f"Excluded from client content (unreviewed model-inferred): "
            f"{summary['excluded_unreviewed_model_inferred']}"
        )
    section_slide(prs, theme, "Provenance & disclosure", bullets)
    # Caveats as a second block on a fresh slide for readability.
    if summary.get("caveats"):
        section_slide(prs, theme, "Caveats", summary["caveats"])


def save_pptx(prs: Presentation) -> bytes:
    import io
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ── DOCX helpers ─────────────────────────────────────────────────────────────
def new_document(theme: Theme, title: str, subtitle: str) -> Document:
    doc = Document()
    h = doc.add_heading(title, level=0)
    for run in h.runs:
        run.font.color.rgb = DocxRGB.from_string(theme.ink)
    sub = doc.add_paragraph(subtitle)
    sub.runs[0].font.size = DocxPt(11)
    sub.runs[0].font.color.rgb = DocxRGB.from_string(theme.muted)
    return doc


def doc_section(doc: Document, heading: str, paragraphs: Sequence[str]) -> None:
    doc.add_heading(heading, level=1)
    for p in paragraphs:
        doc.add_paragraph(p)


def save_docx(doc: Document) -> bytes:
    import io
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
