"""
medicine_manager.py — clinic_app_v5
Improvements over v4:
  - Stock quantity tracking (deducted on prescription)
  - Expiry date tracking with alert query
  - Low-stock alert query
  - Soft delete
"""

from db.database import get_connection, soft_delete
from config import CONFIG
from datetime import datetime, timedelta


def add_medicine(name: str, unit: str, price: float,
                 stock_qty: int = 0, expiry_date: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO medicines (name, unit, price, stock_qty, expiry_date)
               VALUES (?, ?, ?, ?, ?)""",
            (name.strip(), unit.strip(), price, stock_qty, expiry_date)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_all_medicines(include_deleted: bool = False) -> list:
    conn = get_connection()
    try:
        q = "SELECT * FROM medicines"
        if not include_deleted:
            q += " WHERE is_deleted=0"
        q += " ORDER BY name COLLATE NOCASE"
        return conn.execute(q).fetchall()
    finally:
        conn.close()


def update_medicine(med_id: int, name: str, unit: str, price: float,
                    stock_qty: int, expiry_date: str):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE medicines
               SET name=?, unit=?, price=?, stock_qty=?, expiry_date=?
               WHERE id=?""",
            (name.strip(), unit.strip(), price, stock_qty, expiry_date, med_id)
        )
        conn.commit()
    finally:
        conn.close()


def deduct_stock(medicine_id: int, quantity: int):
    """Called when a prescription is saved — reduces stock count."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE medicines SET stock_qty = MAX(0, stock_qty - ?) WHERE id=?",
            (quantity, medicine_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_medicine(med_id: int):
    soft_delete("medicines", med_id)


# ─────────────────────────────────────────────
#  Alert Queries
# ─────────────────────────────────────────────

def get_low_stock_medicines() -> list:
    """Returns medicines at or below the configured low-stock threshold."""
    threshold = CONFIG.get("low_stock_threshold", 10)
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT * FROM medicines
               WHERE is_deleted=0 AND stock_qty <= ?
               ORDER BY stock_qty ASC""",
            (threshold,)
        ).fetchall()
    finally:
        conn.close()


def get_expiring_medicines() -> list:
    """Returns medicines expiring within the configured alert window."""
    days = CONFIG.get("expiry_alert_days", 30)
    alert_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT * FROM medicines
               WHERE is_deleted=0
                 AND expiry_date != ''
                 AND expiry_date IS NOT NULL
                 AND expiry_date <= ?
                 AND expiry_date >= ?
               ORDER BY expiry_date ASC""",
            (alert_date, today)
        ).fetchall()
    finally:
        conn.close()


def get_expired_medicines() -> list:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT * FROM medicines
               WHERE is_deleted=0
                 AND expiry_date != ''
                 AND expiry_date IS NOT NULL
                 AND expiry_date < ?
               ORDER BY expiry_date ASC""",
            (today,)
        ).fetchall()
    finally:
        conn.close()
