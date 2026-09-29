"""A4 PDF renderer for a format-neutral report document."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .model import ReportDocument

PURPLE = colors.HexColor("#520978")
DARK_PURPLE = colors.HexColor("#310F53")
LAVENDER = colors.HexColor("#8A83D1")
PINK = colors.HexColor("#FF0053")
INK = colors.HexColor("#1C1D22")
FONT = "SourceHealthSans"
FONT_BOLD = "SourceHealthSans-Bold"


def _register_fonts() -> None:
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    assets = Path(__file__).with_name("assets")
    pdfmetrics.registerFont(TTFont(FONT, assets / "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, assets / "DejaVuSans-Bold.ttf"))


def _p(text: object, style):
    return Paragraph(escape(str(text)), style)


def render_pdf(document: ReportDocument) -> bytes:
    """Generate a bounded PDF fully in memory."""
    _register_fonts()
    output = BytesIO()
    pdf = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"SourceHealth — {document.repository}",
        author="SourceHealth",
    )
    base = getSampleStyleSheet()
    body = ParagraphStyle("SHBody", parent=base["BodyText"], fontName=FONT, fontSize=9, leading=13, textColor=INK)
    small = ParagraphStyle("SHSmall", parent=body, fontSize=7.5, leading=10)
    title = ParagraphStyle("SHTitle", parent=base["Title"], fontName=FONT_BOLD, fontSize=23, leading=27,
                           textColor=DARK_PURPLE, alignment=TA_CENTER, spaceAfter=8)
    h1 = ParagraphStyle("SHH1", parent=base["Heading1"], fontName=FONT_BOLD, fontSize=15, leading=19,
                        textColor=PURPLE, spaceBefore=12, spaceAfter=7)
    h2 = ParagraphStyle("SHH2", parent=base["Heading2"], fontName=FONT_BOLD, fontSize=11, leading=14,
                        textColor=DARK_PURPLE, spaceBefore=8, spaceAfter=4)
    score_style = ParagraphStyle("SHScore", parent=body, fontName=FONT_BOLD, fontSize=20, leading=24,
                                 alignment=TA_CENTER, textColor=PINK)

    story = [_p("SOURCEHEALTH", h2), _p("Repository Health Report", title), _p(document.repository, title)]
    score = document.health_score if document.health_score is not None else "NO_DATA"
    coverage = f"{document.coverage_percent}%" if document.coverage_percent is not None else "NO_DATA"
    score_table = Table([
        [_p("Repo Health Score", h2), _p("Coverage", h2)],
        [_p(score, score_style), _p(coverage, score_style)],
    ], colWidths=[82 * mm, 82 * mm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F3FA")),
        ("BOX", (0, 0), (-1, -1), 0.7, LAVENDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D4E8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [score_table, Spacer(1, 8), _p("Analysis metadata", h1)]
    metadata = [
        ("Repository", document.repository),
        ("Canonical SourceCraft URL", document.canonical_url),
        ("Analysis ID", document.analysis_id),
        ("Analysis date/time", document.completed_at),
        ("Analysis status", document.status),
        ("Scoring policy", document.scoring_policy_version),
    ]
    metadata_rows = [[_p(label, small), _p(value, body)] for label, value in metadata if value]
    metadata_table = Table(metadata_rows, colWidths=[48 * mm, 116 * mm])
    metadata_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#DDD9E5")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [metadata_table, _p("Category summary", h1)]
    category_rows = [[_p("Category", small), _p("Weight", small), _p("Score", small),
                      _p("Availability", small), _p("Explanation", small)]]
    for category in document.categories:
        category_rows.append([
            _p(category.label, small),
            _p(f"{category.weight}%", small),
            _p(category.score if category.score is not None else "NO_DATA", small),
            _p(category.availability, small),
            _p((category.explanation or "—")[:600], small),
        ])
    category_table = Table(category_rows, colWidths=[31 * mm, 15 * mm, 18 * mm, 28 * mm, 72 * mm], repeatRows=1)
    category_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CFC9D9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F6FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(category_table)
    story += [PageBreak(), _p("Category details", h1)]
    for category in document.categories:
        story += [
            _p(f"{category.label} — {category.weight}%", h2),
            _p(f"Score: {category.score if category.score is not None else 'NO_DATA'} · "
               f"Availability: {category.availability}", body),
            _p(category.explanation or "Explanation is not available in the stored analysis.", body),
        ]
        if category.evidence_refs:
            story.append(_p("Evidence: " + ", ".join(category.evidence_refs), small))

    story.append(_p("Recommendations", h1))
    if document.recommendations:
        for item in document.recommendations:
            story += [
                _p(f"P{item.priority} — {item.title}", h2),
                _p(item.description, body),
                _p("Action: " + (item.action or "—"), body),
            ]
            if item.evidence_refs:
                story.append(_p("Evidence: " + ", ".join(item.evidence_refs), small))
    else:
        story.append(_p("No recommendations are present in the stored analysis.", body))

    story.append(_p("Checks, evidence and limitations", h1))
    for check in document.checks:
        story.append(_p(f"{check.name} — {check.availability}", h2))
        story.append(_p(f"Source: {check.source or 'not specified'} · Findings: {check.finding_count}", body))
        for evidence in check.evidence:
            suffix = evidence.url or evidence.reference
            story.append(_p(f"• {evidence.identifier}: {evidence.summary} ({evidence.source})"
                            + (f" — {suffix}" if suffix else ""), small))
    story.append(_p(
        "NO_DATA means that the stored analysis does not contain enough confirmed data; it is not a zero score. "
        "The document displays the stored analysis and does not recalculate Health Score.", body,
    ))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor("#6D6875"))
        canvas.drawString(17 * mm, 9 * mm, "SourceHealth · Repository Health Report")
        canvas.drawRightString(A4[0] - 17 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
