from datetime import datetime
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as ReportImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


REPORTS_DIR = Path("reports")


def _format_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value)) if value else "None"
    if value in (None, ""):
        return "Not available"
    return escape(str(value))


def _get_result_value(result, key, default="Not available"):
    if not isinstance(result, dict):
        return default
    return result.get(key, default)


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTextWrapped",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetaText",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b"),
        )
    )
    return styles


def _separator():
    table = Table([[""]], colWidths=[7.2 * inch], rowHeights=[1])
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _key_value_table(rows, styles):
    table_data = [
        [
            Paragraph(f"<b>{label}</b>", styles["BodyTextWrapped"]),
            Paragraph(_format_value(value), styles["BodyTextWrapped"]),
        ]
        for label, value in rows
    ]
    table = Table(table_data, colWidths=[2.15 * inch, 5.05 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _image_flowable(image_path):
    if not image_path:
        return None

    source = Path(image_path)
    if not source.exists():
        return None

    try:
        image = ReportImage(str(source))
        max_width = 6.8 * inch
        max_height = 3.5 * inch
        scale = min(max_width / image.imageWidth, max_height / image.imageHeight, 1)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        return image
    except Exception:
        return None


def generate_pdf_report(
    claim_description,
    claim_object,
    image_path,
    result,
    claim_status=None,
    confidence_score=None,
    fraud_risk_score=None,
    risk_level=None,
    estimated_repair_cost=None,
    ai_explanation=None,
):
    """Generate a polished PDF report for a single damage-claim analysis."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    pdf_path = (
        REPORTS_DIR
        / f"claim_report_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.pdf"
    )
    styles = _build_styles()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="AI Damage Claim Verification Report",
    )

    issue_type = _get_result_value(result, "issue_type")
    object_part = _get_result_value(result, "object_part")
    severity = _get_result_value(result, "severity")
    damage_visible = _get_result_value(result, "damage_visible")
    valid_image = _get_result_value(result, "valid_image")
    quality_flags = _get_result_value(result, "quality_flags", [])

    final_assessment = (
        f"The AI review identified issue type '{_format_value(issue_type)}' "
        f"on '{_format_value(object_part)}' with severity '{_format_value(severity)}'. "
        f"Damage visible: {_format_value(damage_visible)}. "
        f"Image valid for review: {_format_value(valid_image)}."
    )

    story = [
        Paragraph("AI Damage Claim Verification System", styles["ReportTitle"]),
        Paragraph(
            f"Report generated on {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            styles["MetaText"],
        ),
        Spacer(1, 10),
        _separator(),
        Paragraph("Claim Overview", styles["SectionHeading"]),
        _key_value_table(
            [
                ("Claim Object", claim_object),
                (
                    "Claim Description",
                    claim_description or "No claim description provided.",
                ),
                ("Claim Status", claim_status or "Not assigned"),
                (
                    "AI Confidence",
                    (
                        f"{confidence_score}%"
                        if confidence_score is not None
                        else "Not available"
                    ),
                ),
                (
                    "Fraud Risk Score",
                    (
                        fraud_risk_score
                        if fraud_risk_score is not None
                        else "Not available"
                    ),
                ),
                ("Risk Level", risk_level or "Not available"),
                ("Estimated Repair Cost", estimated_repair_cost or "Not available"),
            ],
            styles,
        ),
        Paragraph("Uploaded Image", styles["SectionHeading"]),
    ]

    embedded_image = _image_flowable(image_path)
    if embedded_image:
        story.extend([embedded_image, Spacer(1, 8)])
    else:
        story.append(
            Paragraph(
                "Uploaded image could not be embedded in the PDF.",
                styles["BodyTextWrapped"],
            )
        )

    story.extend(
        [
            _separator(),
            Paragraph("AI Analysis Details", styles["SectionHeading"]),
            _key_value_table(
                [
                    ("Issue Type", issue_type),
                    ("Object Part", object_part),
                    ("Severity", severity),
                    ("Damage Visible", damage_visible),
                    ("Valid Image", valid_image),
                    ("Quality Flags", quality_flags),
                ],
                styles,
            ),
            Paragraph("AI Explanation", styles["SectionHeading"]),
            Paragraph(
                ai_explanation or "No additional explanation provided.",
                styles["BodyTextWrapped"],
            ),
            Paragraph("Final AI Assessment", styles["SectionHeading"]),
            Paragraph(final_assessment, styles["BodyTextWrapped"]),
        ]
    )

    doc.build(story)
    return str(pdf_path)
