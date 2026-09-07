"""
pdf_generator.py — clinic_app_v5
Improvements over v4:
  - Reports saved into year/month subfolders automatically
    (reports_output/2026/04/bill_1_20260418.pdf)
  - Prevents the flat folder from accumulating thousands of files
  - Clinic name/doctor from config
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from pathlib import Path
from datetime import datetime
from config import CONFIG


def _get_output_path(filename: str) -> Path:
    """
    Returns a dated subfolder path:
      reports_output/YYYY/MM/filename
    Creates directories as needed.
    """
    base = Path(__file__).parent.parent / CONFIG.get("reports_output_dir", "reports_output")
    now = datetime.now()
    dated = base / str(now.year) / f"{now.month:02d}"
    dated.mkdir(parents=True, exist_ok=True)
    return dated / filename


def generate_bill_pdf(bill_id: int, patient: dict,
                      bill: dict, bill_items: list) -> str:
    """Generate a bill PDF and return the file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bill_{bill_id}_{timestamp}.pdf"
    output_path = _get_output_path(filename)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    styles = getSampleStyleSheet()
    clinic_name_style = ParagraphStyle(
        "ClinicName", fontSize=16, fontName="Helvetica-Bold",
        alignment=TA_CENTER, spaceAfter=4
    )
    sub_style = ParagraphStyle(
        "Sub", fontSize=9, alignment=TA_CENTER, spaceAfter=2
    )
    label_style = ParagraphStyle(
        "Label", fontSize=9, fontName="Helvetica-Bold"
    )
    normal = styles["Normal"]
    normal.fontSize = 9

    elements = []

    # Header
    elements.append(Paragraph(CONFIG.get("clinic_name", "Clinic"), clinic_name_style))
    elements.append(Paragraph(CONFIG.get("doctor_name", ""), sub_style))
    elements.append(Paragraph(CONFIG.get("clinic_address", ""), sub_style))
    elements.append(Paragraph(CONFIG.get("clinic_phone", ""), sub_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 4*mm))

    # Bill info + Patient info side by side
    bill_date = bill["bill_date"][:10] if bill["bill_date"] else ""
    info_data = [
        [Paragraph("<b>Patient:</b>", normal), patient["name"],
         Paragraph("<b>Bill #:</b>", normal), str(bill_id)],
        [Paragraph("<b>Age/Gender:</b>", normal),
         f"{patient.get('age', '')} / {patient.get('gender', '')}",
         Paragraph("<b>Date:</b>", normal), bill_date],
        [Paragraph("<b>Phone:</b>", normal), patient.get("phone", ""),
         "", ""],
    ]
    info_table = Table(info_data, colWidths=[30*mm, 70*mm, 25*mm, 45*mm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 3*mm))

    # Items table
    header = [["#", "Item", "Qty", "Unit Price", "Total"]]
    rows = []
    for i, item in enumerate(bill_items, 1):
        rows.append([
            str(i),
            item["item_name"],
            str(item["quantity"]),
            f"Rs. {item['unit_price']:,.0f}",
            f"Rs. {item['total_price']:,.0f}",
        ])

    items_table = Table(
        header + rows,
        colWidths=[10*mm, 85*mm, 15*mm, 30*mm, 30*mm]
    )
    items_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2C4A7C")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (2, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.grey),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4*mm))

    # Total
    total_data = [
        ["", "", "", Paragraph("<b>Total:</b>", normal),
         Paragraph(f"<b>Rs. {bill['total_amount']:,.0f}</b>", normal)],
    ]
    total_table = Table(total_data, colWidths=[10*mm, 85*mm, 15*mm, 30*mm, 30*mm])
    total_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN",    (3, 0), (-1, -1), "RIGHT"),
        ("LINEABOVE",(3, 0), (-1, 0), 1, colors.black),
    ]))
    elements.append(total_table)

    if bill.get("notes"):
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph(f"<b>Notes:</b> {bill['notes']}", normal))

    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph(
        "Thank you for visiting " + CONFIG.get("clinic_name", "our clinic"),
        ParagraphStyle("Footer", fontSize=8, alignment=TA_CENTER,
                       textColor=colors.grey)
    ))

    doc.build(elements)
    return str(output_path)


def generate_prescription_pdf(visit_id: int, patient: dict,
                               visit: dict, prescriptions: list) -> str:
    """Generate a prescription PDF and return the file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"prescription_{visit_id}_{timestamp}.pdf"
    output_path = _get_output_path(filename)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    styles = getSampleStyleSheet()
    clinic_name_style = ParagraphStyle(
        "ClinicName", fontSize=16, fontName="Helvetica-Bold",
        alignment=TA_CENTER, spaceAfter=4
    )
    sub_style = ParagraphStyle(
        "Sub", fontSize=9, alignment=TA_CENTER, spaceAfter=2
    )
    normal = styles["Normal"]
    normal.fontSize = 9

    elements = []

    elements.append(Paragraph(CONFIG.get("clinic_name", "Clinic"), clinic_name_style))
    elements.append(Paragraph(CONFIG.get("doctor_name", ""), sub_style))
    elements.append(Paragraph(CONFIG.get("clinic_address", ""), sub_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 4*mm))

    # Patient info
    visit_date = visit["visit_date"][:10] if visit["visit_date"] else ""
    info_data = [
        [Paragraph("<b>Patient:</b>", normal), patient["name"],
         Paragraph("<b>Date:</b>", normal), visit_date],
        [Paragraph("<b>Age/Gender:</b>", normal),
         f"{patient.get('age', '')} / {patient.get('gender', '')}",
         Paragraph("<b>Rx #:</b>", normal), str(visit_id)],
    ]
    info_table = Table(info_data, colWidths=[30*mm, 70*mm, 25*mm, 45*mm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 3*mm))

    if visit.get("diagnosis"):
        elements.append(Paragraph(f"<b>Diagnosis:</b> {visit['diagnosis']}", normal))
        elements.append(Spacer(1, 3*mm))

    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 3*mm))

    # Prescriptions table
    rx_data = [["#", "Medicine", "Dosage", "Duration", "Qty"]]
    for i, rx in enumerate(prescriptions, 1):
        rx_data.append([
            str(i),
            rx.get("medicine_name", ""),
            rx.get("dosage", ""),
            rx.get("duration", ""),
            str(rx.get("quantity", 1)),
        ])

    rx_table = Table(rx_data, colWidths=[10*mm, 70*mm, 45*mm, 35*mm, 10*mm])
    rx_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#2C4A7C")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.grey),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(rx_table)

    if visit.get("notes"):
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph(f"<b>Notes:</b> {visit['notes']}", normal))

    elements.append(Spacer(1, 12*mm))
    elements.append(Paragraph(
        f"________________________\n{CONFIG.get('doctor_name', 'Doctor')}",
        ParagraphStyle("Sig", fontSize=9, alignment=TA_RIGHT)
    ))

    doc.build(elements)
    return str(output_path)
