from __future__ import annotations

from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_excel_report_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, dataframe in sheets.items():
            dataframe.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    buffer.seek(0)
    return buffer.getvalue()


def _format_pdf_cell(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _dataframe_to_pdf_table(dataframe: pd.DataFrame, max_rows: int = 12) -> Table:
    preview = dataframe.head(max_rows).copy()
    if preview.empty:
        preview = pd.DataFrame([{"Ghi chú": "Không có dữ liệu"}])

    rows = [list(preview.columns)]
    rows.extend([[_format_pdf_cell(value) for value in row] for row in preview.itertuples(index=False, name=None)])

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b7c9d6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#eaf2f8")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_pdf_report_bytes(title: str, sections: dict[str, pd.DataFrame], subtitle: str | None = None) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.1 * cm,
        title=title,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#1f4e79"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )

    story: list = []
    story.append(Paragraph(title, styles["Title"]))
    if subtitle:
        story.append(Paragraph(subtitle, styles["BodyText"]))
    story.append(Spacer(1, 0.4 * cm))

    for index, (section_name, dataframe) in enumerate(sections.items()):
        if index > 0:
            story.append(PageBreak())
        story.append(Paragraph(section_name, styles["SectionTitle"]))
        story.append(Spacer(1, 0.15 * cm))
        story.append(_dataframe_to_pdf_table(dataframe))
        story.append(Spacer(1, 0.35 * cm))
        story.append(Paragraph(f"Số dòng: {len(dataframe):,}", styles["BodyText"]))

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()
