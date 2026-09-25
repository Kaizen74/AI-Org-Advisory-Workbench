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
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

from .deliverable_theme import Theme

SLIDE_W = Inches(13.333)  # 16:9
SLIDE_H = Inches(7.5)

# Human Agency Scale colours — mirror the Workflow Mapper UI so the deck reads the same.
HAS_COLORS = {
    "H0": "94A3B8", "H1": "2F8074", "H2": "5FB3A6",
    "H3": "9FCABF", "H4": "CBD5E1", "H5": "E2E8F0",
}
# AI-opportunity index weights — the SAME formula the Workflow Mapper UI shows (index = mean × 100).
HAS_WEIGHTS = {"H0": 0.0, "H1": 1.0, "H2": 0.75, "H3": 0.5, "H4": 0.25, "H5": 0.0}
# Human Agency band names + go/no-go zone labels & dot colours — mirror the UI's HAS / ZONE_META maps
# so a deck legend and an on-screen legend read identically.
HAS_NAMES = {
    "H0": "Robotics / GSE lever", "H1": "AI handles entirely", "H2": "AI with minimal input",
    "H3": "Equal partnership", "H4": "Human-led, AI assists", "H5": "Human essential",
}
ZONE_META = {
    "GREEN_LIGHT": ("Green light", "2F8074"),
    "RED_LIGHT": ("Red light", "C2683F"),
    "ROBOTICS_GSE_LEVER": ("Robotics lever", "7C8DB5"),
    "NO_BENCHMARK_MATCH": ("No benchmark", "94A3B8"),
}
REVIEW_COLORS = {"approved": "3F9D77"}  # anything else = amber 'unreviewed', as on the board
REVIEW_UNREVIEWED = "CBB24A"


def has_index(bands: dict) -> int:
    """Index 0-100 from a band-count map — identical to the frontend's indexFromBands."""
    total = sum(bands.get(b, 0) for b in HAS_WEIGHTS)
    if not total:
        return 0
    return round(sum(bands.get(b, 0) * w for b, w in HAS_WEIGHTS.items()) / total * 100)


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


def _card_text(shape, theme: Theme, text: str, role: str, band: str,
               zone: str = "", review_state: str = "") -> None:
    """Card body — the deck twin of the on-screen TaskCard: task text, role · H-band, then the
    zone chip and review state the card footer shows (D49)."""
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.04)
    tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = (text[:60] + "…") if len(text) > 60 else text
    r.font.size = Pt(8.5)
    r.font.name = theme.body_font
    r.font.color.rgb = _rgb(theme.ink)
    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    r2.text = f"{role}  ·  {band}"
    r2.font.size = Pt(7.5)
    r2.font.name = theme.body_font
    r2.font.color.rgb = _rgb(theme.muted)
    if zone or review_state:
        p3 = tf.add_paragraph()
        if zone:
            label, color = ZONE_META.get(zone, (zone, "CBD5E1"))
            rz = p3.add_run()
            rz.text = f"● {label}"
            rz.font.size = Pt(7)
            rz.font.name = theme.body_font
            rz.font.color.rgb = _rgb(color)
        if review_state:
            rv = p3.add_run()
            rv.text = f"   ● {review_state}"
            rv.font.size = Pt(7)
            rv.font.name = theme.body_font
            rv.font.color.rgb = _rgb(REVIEW_COLORS.get(review_state, REVIEW_UNREVIEWED))


def workflow_board_slide(prs: Presentation, theme: Theme, name: str, value_stream: str,
                         steps: Sequence[dict], mapped: int, total: int, unmapped: int,
                         page: int = 1, pages: int = 1,
                         unmapped_tasks: Sequence[dict] = ()) -> None:
    """Draw a process as a visual board: step columns of task cards (coloured by Human Agency band)
    with arrows between steps — the deck mirror of the Workflow Mapper UI. When `unmapped_tasks` is
    given (page 1), the dashed 'Unmapped tasks' tray is drawn as the leading column, exactly where
    the board shows it (D49)."""
    slide = _blank(prs)
    heading = name + (f"  ·  {value_stream}" if value_stream else "")
    if pages > 1:
        heading += f"   (steps {page}/{pages})"
    _textbox(slide, Inches(0.5), Inches(0.45), Inches(12.3), Inches(0.8), heading,
             size=24, color=theme.ink, font=theme.title_font)
    _accent_rule(slide, theme, top=Inches(1.25), left=Inches(0.5), width=Inches(1.4))

    if not steps and not unmapped_tasks:
        _textbox(slide, Inches(0.5), Inches(2.0), Inches(11), Inches(0.6),
                 "No steps yet — build them in the Workflow Mapper.", size=14, color=theme.muted,
                 font=theme.body_font)
        return

    # Columns = the optional unmapped tray (leading, as on screen) + this page's step columns.
    tray = [{"tray": True, "name": "Unmapped tasks", "tasks": list(unmapped_tasks)}] \
        if unmapped_tasks else []
    columns = tray + [dict(s, tray=False) for s in steps]
    cols = len(columns)
    left0, top0 = Inches(0.5), Inches(1.7)
    gap = Inches(0.34)
    colw = int((Inches(12.3) - gap * (cols - 1)) / cols)
    header_h = Inches(0.5)
    card_h, card_gap = Inches(0.78), Inches(0.12)
    max_cards = 5

    for i, col in enumerate(columns):
        left = left0 + i * (colw + gap)
        is_tray = col.get("tray")
        tasks = col.get("tasks", [])
        # column header — carries the card count, like the on-screen column header
        hdr = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top0, colw, header_h)
        hdr.fill.solid()
        hdr.fill.fore_color.rgb = _rgb("F1F5F9" if is_tray else theme.ink)
        if is_tray:
            hdr.line.color.rgb = _rgb("CBD5E1"); hdr.line.width = Pt(1)
        else:
            hdr.line.fill.background()
        htf = hdr.text_frame; htf.word_wrap = True
        hp = htf.paragraphs[0]; hr = hp.add_run()
        label = "Unmapped tasks" if is_tray else f"{col.get('seq', i)}.  {col.get('name', '')}"
        hr.text = f"{label}   ({len(tasks)})"
        hr.font.size = Pt(11); hr.font.bold = True; hr.font.name = theme.title_font
        hr.font.color.rgb = _rgb(theme.muted if is_tray else theme.ground)
        # arrow to the next step (never out of the tray — the tray isn't part of the flow)
        if not is_tray and i < cols - 1:
            arr = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left + colw + Emu(20000),
                                         top0 + Inches(0.12), gap - Emu(40000), Inches(0.26))
            arr.fill.solid(); arr.fill.fore_color.rgb = _rgb(theme.muted)
            arr.line.fill.background()
        # task cards
        y = top0 + header_h + Inches(0.12)
        for t in tasks[:max_cards]:
            band = t.get("human_agency_level", "H0")
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, y, colw, card_h)
            card.fill.solid(); card.fill.fore_color.rgb = _rgb("FFFFFF")
            card.line.color.rgb = _rgb(HAS_COLORS.get(band, "CBD5E1"))
            card.line.width = Pt(1.5)
            _card_text(card, theme, t.get("text", ""), t.get("role", ""), band,
                       zone=t.get("zone") or "", review_state=t.get("review_state") or "")
            y += card_h + card_gap
        if not tasks:
            _textbox(slide, left, y, colw, Inches(0.4),
                     "(nothing unmapped)" if is_tray else "(no tasks linked)",
                     size=9, color=theme.muted, font=theme.body_font)
        elif len(tasks) > max_cards:
            _textbox(slide, left, y, colw, Inches(0.3), f"+{len(tasks) - max_cards} more",
                     size=8, color=theme.muted, font=theme.body_font)

    _textbox(slide, Inches(0.5), Inches(7.0), Inches(12), Inches(0.4),
             f"Mapped {mapped} / {total} tasks  ·  {unmapped} unmapped   "
             "·   colour = Human Agency (H0 robotics → H5 human-led)   "
             "·   ● zone (go / no-go)   ·   ● review state",
             size=10, color=theme.muted, font=theme.body_font)


def landscape_slide(prs: Presentation, theme: Theme, points: Sequence[dict],
                    unscored: int = 0) -> None:
    """The AI-opportunity landscape (capability × worker desire) — the deck mirror of the Workflow
    Mapper's Landscape view. Quadrants carry the WORKBank zone names (arXiv:2506.06576, D47):
    Green Light (high cap + high desire), Red Light (high cap + low desire), R&D Opportunity,
    Low Priority. `points`: [{capability, desire|None, band}]; desire None → neutral 0.5, hollow dot.
    Scalable: dots capped at 250 (a '+N more' note covers the rest)."""
    slide = _blank(prs)
    _textbox(slide, Inches(0.5), Inches(0.45), Inches(12.3), Inches(0.8),
             "AI opportunity landscape", size=24, color=theme.ink, font=theme.title_font)
    _accent_rule(slide, theme, top=Inches(1.25), left=Inches(0.5), width=Inches(1.4))

    if not points:
        _textbox(slide, Inches(0.5), Inches(2.0), Inches(11), Inches(0.6),
                 "No capability-scored tasks yet — run Task Intelligence → AI opportunity.",
                 size=14, color=theme.muted, font=theme.body_font)
        return

    # Plot area
    px, py, pw, ph = Inches(1.5), Inches(1.7), Inches(8.6), Inches(4.9)
    plot = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px, py, pw, ph)
    plot.fill.solid(); plot.fill.fore_color.rgb = _rgb("FFFFFF")
    plot.line.color.rgb = _rgb("E2E8F0"); plot.line.width = Pt(1)
    # Quadrant split lines
    for ln in (slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px + int(pw / 2), py, Emu(9000), ph),
               slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px, py + int(ph / 2), pw, Emu(9000))):
        ln.fill.solid(); ln.fill.fore_color.rgb = _rgb("EEF1F4"); ln.line.fill.background()
    # WORKBank quadrant labels (correct orientation — D47): x = capability →, y = desire ↑.
    quad = [("R&D opportunity", px, py, "9A6A18", False),
            ("Green light — automate", px + int(pw / 2), py, "3D8273", True),
            ("Low priority", px, py + int(ph / 2), "94A3B8", False),
            ("Red light — caution", px + int(pw / 2), py + int(ph / 2), "A04D2E", True)]
    for label, qx, qy, color, right in quad:
        box = _textbox(slide, qx + Inches(0.08), qy + Inches(0.05), int(pw / 2) - Inches(0.16),
                       Inches(0.3), label.upper(), size=9, color=color, bold=True,
                       font=theme.body_font)
        if right:
            from pptx.enum.text import PP_ALIGN
            box.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
    # Dots (band-coloured; hollow = desire not captured, at neutral height — mirrors the UI)
    MAX_DOTS = 250
    d = Inches(0.13)
    for pt_ in list(points)[:MAX_DOTS]:
        cap = max(0.0, min(1.0, float(pt_.get("capability") or 0.0)))
        desire = pt_.get("desire")
        y_val = max(0.0, min(1.0, float(desire))) if desire is not None else 0.5
        band = pt_.get("band", "H0")
        # Centre the dot on its coordinate (shapes are placed by top-left corner), so a dot at
        # capability 0.5 straddles the quadrant divide exactly as it does on screen.
        cx = px + int(cap * pw) - int(d / 2)
        cy = py + int((1.0 - y_val) * ph) - int(d / 2)  # pptx y grows down; desire grows up
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, cx, cy, d, d)
        color = HAS_COLORS.get(band, "CBD5E1")
        dot.fill.solid()
        dot.fill.fore_color.rgb = _rgb("FFFFFF" if desire is None else color)
        dot.line.color.rgb = _rgb(color)
        dot.line.width = Pt(1.75 if desire is None else 1.0)
    # Axes + legend
    _textbox(slide, px, py + ph + Inches(0.08), pw, Inches(0.3),
             "Automation capability →", size=10, color=theme.muted, font=theme.body_font)
    _textbox(slide, Inches(0.55), py + Inches(1.6), Inches(0.9), Inches(1.6),
             "Worker desire →", size=10, color=theme.muted, font=theme.body_font)
    legend_y = Inches(1.7)
    for i, b in enumerate(("H1", "H2", "H3", "H4", "H5", "H0")):
        sw = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(10.4), legend_y + i * Inches(0.34),
                                    Inches(0.16), Inches(0.16))
        sw.fill.solid(); sw.fill.fore_color.rgb = _rgb(HAS_COLORS[b]); sw.line.fill.background()
        _textbox(slide, Inches(10.65), legend_y + i * Inches(0.34) - Inches(0.045), Inches(2.6),
                 Inches(0.3), f"{b}  {HAS_NAMES[b]}", size=9, color=theme.ink,
                 font=theme.body_font)
    notes = ["hollow dot = local desire not captured (neutral height)",
             "quadrants per Stanford WORKBank (desire × capability)"]
    if len(points) > MAX_DOTS:
        notes.insert(0, f"showing {MAX_DOTS} of {len(points)} scored tasks")
    if unscored:
        notes.append(f"{unscored} task(s) not yet capability-scored (not plotted)")
    _textbox(slide, Inches(0.5), Inches(7.0), Inches(12.3), Inches(0.4),
             "  ·  ".join(notes), size=9, color=theme.muted, font=theme.body_font)


def org_rollup_slide(prs: Presentation, theme: Theme, rows: Sequence[dict],
                     org_index: int, page: int = 1, pages: int = 1,
                     stats: Sequence[Tuple[str, str]] = ()) -> None:
    """One page of the org-hierarchy Roll-up — the deck mirror of the Workflow Mapper's Roll-up view.
    Each row: depth-indented role, own/team task counts, rolled-up index, and an H-mix stacked bar.
    `rows`: [{title, name, depth, own, team, reviewed_pct, index, bands}] in depth-first order.
    `stats`: the view's org-wide stat cards (People / Reporting layers / …), drawn on page 1."""
    slide = _blank(prs)
    heading = "Org-hierarchy AI roll-up" + (f"   (page {page}/{pages})" if pages > 1 else "")
    _textbox(slide, Inches(0.5), Inches(0.45), Inches(9.6), Inches(0.8), heading,
             size=24, color=theme.ink, font=theme.title_font)
    _textbox(slide, Inches(10.2), Inches(0.5), Inches(2.6), Inches(0.8),
             f"Org index  {org_index}/100", size=16, color=theme.accent, bold=True,
             font=theme.title_font)
    _accent_rule(slide, theme, top=Inches(1.25), left=Inches(0.5), width=Inches(1.4))

    top0, row_h = Inches(1.6), Inches(0.42)
    if stats:
        # The four stat cards that head the Roll-up view on screen.
        cw, cgap = Inches(2.9), Inches(0.24)
        for i, (label, value) in enumerate(stats[:4]):
            cx = Inches(0.5) + i * (cw + cgap)
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.5), cw,
                                          Inches(0.72))
            card.fill.solid(); card.fill.fore_color.rgb = _rgb("FFFFFF")
            card.line.color.rgb = _rgb("E2E8F0"); card.line.width = Pt(1)
            _textbox(slide, cx + Inches(0.14), Inches(1.56), cw - Inches(0.2), Inches(0.24),
                     label.upper(), size=8, color=theme.muted, font=theme.body_font)
            _textbox(slide, cx + Inches(0.14), Inches(1.76), cw - Inches(0.2), Inches(0.4),
                     str(value), size=16, color=theme.ink, bold=True, font=theme.title_font)
        top0 = Inches(2.44)
    bar_x, bar_w = Inches(9.0), Inches(2.4)
    for i, r in enumerate(rows):
        y = top0 + i * row_h
        indent = Inches(0.5) + min(int(r.get("depth", 0)), 6) * Inches(0.32)
        title = r.get("title", "—")
        label = (title[:48] + "…") if len(title) > 48 else title
        # role + its org level — the title and L-chip the on-screen row shows.
        _textbox(slide, indent, y, Inches(5.6) - (indent - Inches(0.5)), Inches(0.36),
                 f"{label}   L{r.get('level', 0)}", size=11, color=theme.ink,
                 font=theme.body_font)
        _textbox(slide, Inches(6.1), y, Inches(1.6), Inches(0.36),
                 f"{r.get('own', 0)} own · {r.get('team', 0)} team", size=9, color=theme.muted,
                 font=theme.body_font)
        _textbox(slide, Inches(7.7), y, Inches(0.7), Inches(0.36),
                 str(r.get("index", 0)), size=12, color=theme.accent, bold=True,
                 font=theme.title_font)
        _textbox(slide, Inches(8.3), y, Inches(0.7), Inches(0.36),
                 f"{r.get('reviewed_pct', 0)}%", size=9, color=theme.muted, font=theme.body_font)
        # H-mix stacked bar (rolled-up team mix — same encoding as the UI)
        bands = r.get("bands", {})
        total = sum(bands.get(b, 0) for b in HAS_WEIGHTS) or 1
        x = bar_x
        for b in ("H0", "H1", "H2", "H3", "H4", "H5"):
            c = bands.get(b, 0)
            if not c:
                continue
            w = int(bar_w * (c / total))
            if w <= 0:
                continue
            seg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y + Inches(0.10), w, Inches(0.16))
            seg.fill.solid(); seg.fill.fore_color.rgb = _rgb(HAS_COLORS[b])
            seg.line.fill.background()
            x += w
    _textbox(slide, Inches(0.5), Inches(7.0), Inches(12.3), Inches(0.4),
             "index & bar = this role + all reports (rolled up the reporting line)  ·  "
             "own = the role's personal tasks  ·  % = reviewed share  ·  bar colour = H0→H5",
             size=9, color=theme.muted, font=theme.body_font)


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
