"""
billing_manager.py — clinic_app_v5
Manages bills and bill items.
Adds monthly revenue summary for the dashboard.
"""

from db.database import get_connection, soft_delete
from datetime import datetime


def create_bill(visit_id: int, patient_id: int,
                items: list[dict], notes: str = "") -> int:
    """
    items: list of dicts with:
        item_type ('service'|'medicine'), item_id, item_name,
        quantity, unit_price, total_price
    """
    total = sum(i.get("total_price", 0) for i in items)
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO bills
                   (visit_id, patient_id, total_amount, paid_amount, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (visit_id, patient_id, total, total, notes)
        )
        bill_id = cur.lastrowid

        for item in items:
            conn.execute(
                """INSERT INTO bill_items
                       (bill_id, item_type, item_id, item_name,
                        quantity, unit_price, total_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (bill_id,
                 item["item_type"],
                 item.get("item_id"),
                 item["item_name"],
                 item.get("quantity", 1),
                 item.get("unit_price", 0),
                 item.get("total_price", 0))
            )

        conn.commit()
        return bill_id
    finally:
        conn.close()


def get_bill_by_id(bill_id: int) -> dict | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM bills WHERE id=?", (bill_id,)
        ).fetchone()
    finally:
        conn.close()


def get_bill_items(bill_id: int) -> list:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM bill_items WHERE bill_id=?", (bill_id,)
        ).fetchall()
    finally:
        conn.close()


def get_bills_for_patient(patient_id: int) -> list:
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT * FROM bills
               WHERE patient_id=? AND is_deleted=0
               ORDER BY bill_date DESC""",
            (patient_id,)
        ).fetchall()
    finally:
        conn.close()


def delete_bill(bill_id: int):
    soft_delete("bills", bill_id)


# ─────────────────────────────────────────────
#  Dashboard / Reports
# ─────────────────────────────────────────────

def get_monthly_summary(year: int, month: int) -> dict:
    """Returns revenue and patient count for a given month."""
    prefix = f"{year}-{month:02d}"
    conn = get_connection()
    try:
        revenue = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0)
               FROM bills
               WHERE is_deleted=0 AND bill_date LIKE ?""",
            (f"{prefix}%",)
        ).fetchone()[0]

        patient_count = conn.execute(
            """SELECT COUNT(DISTINCT patient_id)
               FROM visits
               WHERE is_deleted=0 AND visit_date LIKE ?""",
            (f"{prefix}%",)
        ).fetchone()[0]

        visit_count = conn.execute(
            """SELECT COUNT(*)
               FROM visits
               WHERE is_deleted=0 AND visit_date LIKE ?""",
            (f"{prefix}%",)
        ).fetchone()[0]

        return {
            "month":         f"{year}-{month:02d}",
            "revenue":       revenue,
            "patient_count": patient_count,
            "visit_count":   visit_count,
        }
    finally:
        conn.close()


def get_last_12_months_summary() -> list[dict]:
    from datetime import date
    from dateutil.relativedelta import relativedelta
    results = []
    today = date.today()
    for i in range(11, -1, -1):
        d = today - relativedelta(months=i)
        results.append(get_monthly_summary(d.year, d.month))
    return results


def get_today_summary() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        revenue = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) FROM bills
               WHERE is_deleted=0 AND bill_date LIKE ?""",
            (f"{today}%",)
        ).fetchone()[0]

        visits = conn.execute(
            """SELECT COUNT(*) FROM visits
               WHERE is_deleted=0 AND visit_date LIKE ?""",
            (f"{today}%",)
        ).fetchone()[0]

        return {"date": today, "revenue": revenue, "visits": visits}
    finally:
        conn.close()
