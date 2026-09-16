"""
pdf_generator.py — clinic_app_v6

NEW in v6 — the prescription is redesigned with:
  - Clinic logo (if CONFIG["clinic_logo_path"] points at an image that
    exists — drop a file at assets/logo.png) next to the clinic header
  - A colored "PRESCRIPTION" document badge with date + Rx number
  - A patient info bar (name, age/gender, phone)
  - A vitals row — BP, Temperature, Weight — shown as small stat cards
    (only the ones that were actually recorded are shown)
  - A highlighted Diagnosis box
  - A cleaner, better-spaced medicines (Rx) table
  - A Notes box and a signature footer

The bill PDF keeps its original layout/fields, just reskinned with the
same branded header for a consistent look between the two documents.

Other things carried over from v5:
  - Reports saved into year/month subfolders automatically
    (reports_output/2026/09/prescription_1_20260909.pdf)
  - Clinic name/doctor/address/phone from config.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from pathlib import Path
from datetime import datetime
from config import CONFIG
import sys
import os
import subprocess

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


def open_pdf(filepath: str):
    """
    Open a generated PDF in the OS's default viewer (ported from v4).

    IMPORTANT: uses Popen, not call/run — call() blocks until the
    viewer process exits, which freezes the whole app for as long as
    the PDF viewer stays open (or hangs forever if xdg-open can't find
    a handler and the app has no console for it to report to). Popen
    launches the viewer and returns immediately either way.
    """
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", filepath],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", filepath],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    except Exception as e:
        # Never let "couldn't launch a viewer" take down the app — the
        # PDF is already saved on disk either way; the caller shows its
        # own warning dialog if this raises.
        raise RuntimeError(f"Could not open a PDF viewer: {e}")


# ── Palette ────────────────────────────────────────────────────────
PRIMARY       = colors.HexColor("#2C4A7C")   # unchanged from v5 — kept for
PRIMARY_LIGHT = colors.HexColor("#EEF3FA")   # brand consistency with the rest
ACCENT        = colors.HexColor("#0F8B8D")   # of the app (login screen, etc.)
ACCENT_LIGHT  = colors.HexColor("#E7F6F6")
TEXT_DARK     = colors.HexColor("#1A2333")
TEXT_MUTED    = colors.HexColor("#6B7280")
BORDER_GRAY   = colors.HexColor("#D8DEE9")
ROW_ALT       = colors.HexColor("#F7F9FC")
DUE_RED       = colors.HexColor("#B91C1C")

PAGE_WIDTH_MM = 180   # usable width after 15mm margins on both sides


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


# ─────────────────────────────────────────────
#  Shared branded header (logo + clinic info + document badge)
# ─────────────────────────────────────────────

def _get_logo_flowable(max_w_mm=22, max_h_mm=22):
    """Loads the clinic logo at its correct aspect ratio, or returns None
    if PIL isn't available / no logo has been placed at clinic_logo_path."""
    if PILImage is None:
        return None
    path = Path(__file__).parent.parent / CONFIG.get("clinic_logo_path", "assets/logo.png")
    if not path.exists():
        return None
    try:
        with PILImage.open(path) as im:
            w, h = im.size
        scale = min((max_w_mm * mm) / w, (max_h_mm * mm) / h)
        return RLImage(str(path), width=w * scale, height=h * scale)
    except Exception:
        return None


def _build_header(doc_title: str, meta_lines: list) -> list:
    """
    Shared header for both documents:
      [ logo ]  Clinic Name              [ PRESCRIPTION  ]
                Dr. So-and-so            [ Date: ...     ]
                Address, phone           [ Rx#/Bill#: N  ]
      ───────────────────────────────────────────────────  (accent rule)
    """
    clinic_name_style = ParagraphStyle(
        "ClinicName", fontSize=17, fontName="Helvetica-Bold",
        textColor=PRIMARY, leading=20
    )
    doctor_style = ParagraphStyle(
        "Doctor", fontSize=10.5, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, leading=13
    )
    contact_style = ParagraphStyle(
        "Contact", fontSize=8.5, textColor=TEXT_MUTED, leading=11
    )
    badge_title_style = ParagraphStyle(
        "BadgeTitle", fontSize=12.5, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=TA_CENTER, leading=15
    )
    badge_meta_style = ParagraphStyle(
        "BadgeMeta", fontSize=8.5, textColor=colors.white,
        alignment=TA_CENTER, leading=12
    )

    clinic_block = [
        Paragraph(CONFIG.get("clinic_name", "Clinic"), clinic_name_style),
        Paragraph(CONFIG.get("doctor_name", ""), doctor_style),
        Paragraph(CONFIG.get("clinic_address", ""), contact_style),
        Paragraph(CONFIG.get("clinic_phone", ""), contact_style),
    ]

    badge_content = [Paragraph(doc_title, badge_title_style)]
    for line in meta_lines:
        badge_content.append(Spacer(1, 2))
        badge_content.append(Paragraph(line, badge_meta_style))
    badge = Table([[badge_content]], colWidths=[50 * mm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    logo = _get_logo_flowable()
    if logo is not None:
        row = [[logo, clinic_block, badge]]
        col_widths = [24 * mm, 96 * mm, 60 * mm]
    else:
        row = [[clinic_block, badge]]
        col_widths = [120 * mm, 60 * mm]

    header_table = Table(row, colWidths=col_widths)
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    rule = Table([[""]], colWidths=[PAGE_WIDTH_MM * mm], rowHeights=[2.4])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PRIMARY)]))

    return [header_table, Spacer(1, 3 * mm), rule, Spacer(1, 5 * mm)]


def _patient_info_bar(patient: dict) -> Table:
    """A light shaded info strip: Patient / Age-Gender / Phone."""
    label_style = ParagraphStyle("InfoLabel", fontSize=8, fontName="Helvetica-Bold",
                                  textColor=TEXT_MUTED)
    value_style = ParagraphStyle("InfoValue", fontSize=9.5, fontName="Helvetica-Bold",
                                  textColor=TEXT_DARK)
    data = [[
        Paragraph("PATIENT", label_style),
        Paragraph(patient.get("name", "") or "—", value_style),
        Paragraph("AGE / GENDER", label_style),
        Paragraph(f"{patient.get('age', '') or '—'} / {patient.get('gender', '') or '—'}", value_style),
        Paragraph("PHONE", label_style),
        Paragraph(patient.get("phone", "") or "—", value_style),
    ]]
    table = Table(data, colWidths=[22 * mm, 46 * mm, 28 * mm, 30 * mm, 18 * mm, 26 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _vitals_row(visit: dict):
    """Small stat cards for BP / Temperature / Weight. Only vitals that
    were actually recorded are shown; returns None if none were."""
    candidates = [
        ("BLOOD PRESSURE", visit.get("bp") or ""),
        ("TEMPERATURE", visit.get("temperature") or ""),
        ("WEIGHT", visit.get("weight") or ""),
    ]
    items = [(label, value) for label, value in candidates if value]
    if not items:
        return None

    label_style = ParagraphStyle("VLabel", fontSize=7.5, fontName="Helvetica-Bold",
                                  textColor=ACCENT, alignment=TA_CENTER)
    value_style = ParagraphStyle("VValue", fontSize=13, fontName="Helvetica-Bold",
                                  textColor=TEXT_DARK, alignment=TA_CENTER)

    cells = [[Paragraph(label, label_style), Paragraph(value, value_style)]
             for label, value in items]
    # Transpose into a single row of stacked (label, value) cells
    row = [[cell for cell in cells]]
    col_width = (PAGE_WIDTH_MM * mm) / len(items)

    table = Table(row, colWidths=[col_width] * len(items))
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]
    for i in range(1, len(items)):
        style.append(("LINEBEFORE", (i, 0), (i, 0), 1, colors.white))
    table.setStyle(TableStyle(style))
    return table


def _labeled_box(label: str, text: str, accent=PRIMARY, bg=PRIMARY_LIGHT) -> Table:
    """A card with a colored left accent bar — used for Diagnosis / Notes."""
    label_p = Paragraph(label, ParagraphStyle(
        "BoxLabel", fontSize=8.5, fontName="Helvetica-Bold", textColor=accent, spaceAfter=3))
    text_p = Paragraph(text or "—", ParagraphStyle(
        "BoxText", fontSize=9.5, textColor=TEXT_DARK, leading=13))

    inner = Table([[label_p], [text_p]], colWidths=[(PAGE_WIDTH_MM - 4) * mm])
    inner.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))

    box = Table([[inner]], colWidths=[PAGE_WIDTH_MM * mm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return box


def _footer_note(text: str) -> Paragraph:
    return Paragraph(text, ParagraphStyle(
        "Footer", fontSize=7.5, alignment=TA_CENTER, textColor=TEXT_MUTED))


# ─────────────────────────────────────────────
#  Bill PDF  (same fields as v5, reskinned with the shared header)
# ─────────────────────────────────────────────

def generate_bill_pdf(bill_id: int, patient: dict,
                      bill: dict, bill_items: list) -> str:
    """Generate a bill PDF and return the file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bill_{bill_id}_{timestamp}.pdf"
    output_path = _get_output_path(filename)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=15 * mm
    )

    normal = ParagraphStyle("Normal9", fontSize=9.5, leading=12)
    bill_date = (bill.get("bill_date") or "")[:10]

    elements = []
    elements += _build_header("BILL / RECEIPT", [f"Date: {bill_date}", f"Bill #: {bill_id}"])
    elements.append(_patient_info_bar(patient))
    elements.append(Spacer(1, 5 * mm))

    header = [["#", "ITEM", "QTY", "UNIT PRICE", "TOTAL"]]
    rows = []
    for i, item in enumerate(bill_items, 1):
        rows.append([
            str(i),
            item["item_name"],
            str(item["quantity"]),
            f"Rs. {item['unit_price']:,.0f}",
            f"Rs. {item['total_price']:,.0f}",
        ])
    items_table = Table(header + rows, colWidths=[10 * mm, 85 * mm, 15 * mm, 30 * mm, 30 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
        ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 9),
        ("ALIGN",          (2, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ("GRID",           (0, 0), (-1, -1), 0.4, BORDER_GRAY),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    total_data = [
        ["", "", "", Paragraph("<b>Total:</b>", normal),
         Paragraph(f"<b>Rs. {bill['total_amount']:,.0f}</b>", normal)],
    ]
    total_table = Table(total_data, colWidths=[10 * mm, 85 * mm, 15 * mm, 30 * mm, 30 * mm])
    total_table.setStyle(TableStyle([
        ("FONTSIZE",  (0, 0), (-1, -1), 10),
        ("ALIGN",     (3, 0), (-1, -1), "RIGHT"),
        ("LINEABOVE", (3, 0), (-1, 0), 1, PRIMARY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(total_table)

    if bill.get("notes"):
        elements.append(Spacer(1, 4 * mm))
        elements.append(_labeled_box("NOTES", bill["notes"], accent=ACCENT, bg=ACCENT_LIGHT))

    elements.append(Spacer(1, 8 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY))
    elements.append(Spacer(1, 2 * mm))
    elements.append(_footer_note("Thank you for visiting " + CONFIG.get("clinic_name", "our clinic")))

    doc.build(elements)
    return str(output_path)


# ─────────────────────────────────────────────
#  Prescription PDF  (redesigned)
# ─────────────────────────────────────────────

def generate_prescription_pdf(visit_id: int, patient: dict,
                               visit: dict, prescriptions: list) -> str:
    """Generate a prescription PDF and return the file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"prescription_{visit_id}_{timestamp}.pdf"
    output_path = _get_output_path(filename)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=15 * mm
    )

    visit_date = (visit.get("visit_date") or "")[:10]

    elements = []
    elements += _build_header("PRESCRIPTION", [f"Date: {visit_date}", f"Rx #: {visit_id}"])
    elements.append(_patient_info_bar(patient))
    elements.append(Spacer(1, 4 * mm))

    vitals = _vitals_row(visit)
    if vitals is not None:
        elements.append(vitals)
        elements.append(Spacer(1, 4 * mm))

    if visit.get("diagnosis"):
        elements.append(_labeled_box("DIAGNOSIS", visit["diagnosis"]))
        elements.append(Spacer(1, 5 * mm))

    elements.append(Paragraph(
        "Rx &nbsp;PRESCRIBED MEDICINES",
        ParagraphStyle("RxHeading", fontSize=11, fontName="Helvetica-Bold",
                       textColor=PRIMARY, spaceAfter=4)
    ))

    rx_header = [["#", "MEDICINE", "DOSAGE", "DURATION", "QTY"]]
    rx_rows = []
    for i, rx in enumerate(prescriptions, 1):
        rx_rows.append([
            str(i),
            rx.get("medicine_name", "") or "—",
            rx.get("dosage", "") or "—",
            rx.get("duration", "") or "—",
            str(rx.get("quantity", 1)),
        ])
    if not rx_rows:
        rx_rows = [["—", "No medicines prescribed for this visit.", "", "", ""]]

    rx_table = Table(rx_header + rx_rows, colWidths=[10 * mm, 65 * mm, 40 * mm, 40 * mm, 15 * mm])
    rx_table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
        ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 9),
        ("ALIGN",          (0, 0), (0, -1), "CENTER"),
        ("ALIGN",          (-1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
        ("GRID",           (0, 0), (-1, -1), 0.4, BORDER_GRAY),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
    ]))
    elements.append(rx_table)

    if visit.get("notes"):
        elements.append(Spacer(1, 5 * mm))
        elements.append(_labeled_box("NOTES", visit["notes"], accent=ACCENT, bg=ACCENT_LIGHT))

    elements.append(Spacer(1, 16 * mm))
    sig_table = Table(
        [["", Paragraph(
            f"_______________________<br/><b>{CONFIG.get('doctor_name', 'Doctor')}</b>",
            ParagraphStyle("Sig", fontSize=9, alignment=TA_RIGHT, leading=13)
        )]],
        colWidths=[(PAGE_WIDTH_MM - 60) * mm, 60 * mm]
    )
    sig_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    elements.append(sig_table)

    elements.append(Spacer(1, 6 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY))
    elements.append(Spacer(1, 2 * mm))
    elements.append(_footer_note(
        f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')} • "
        f"{CONFIG.get('clinic_name', '')} — for consultation purposes only."
    ))

    doc.build(elements)
    return str(output_path)
