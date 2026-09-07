"""
visit_manager.py — clinic_app_v5
Manages patient visits and prescriptions.
Deducts medicine stock when prescriptions are saved.
"""

from db.database import get_connection, soft_delete
from core.medicine_manager import deduct_stock
from datetime import datetime


def add_visit(patient_id: int, symptoms: str,
              diagnosis: str, notes: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO visits (patient_id, symptoms, diagnosis, notes)
               VALUES (?, ?, ?, ?)""",
            (patient_id, symptoms, diagnosis, notes)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def save_prescriptions(visit_id: int, prescriptions: list[dict]):
    """
    prescriptions: list of dicts with keys:
        medicine_id, dosage, duration, quantity
    Deducts stock for each medicine saved.
    """
    conn = get_connection()
    try:
        # Remove existing prescriptions for this visit (re-save pattern)
        conn.execute("DELETE FROM prescriptions WHERE visit_id=?", (visit_id,))

        for rx in prescriptions:
            conn.execute(
                """INSERT INTO prescriptions
                       (visit_id, medicine_id, dosage, duration, quantity)
                   VALUES (?, ?, ?, ?, ?)""",
                (visit_id,
                 rx["medicine_id"],
                 rx.get("dosage", ""),
                 rx.get("duration", ""),
                 rx.get("quantity", 1))
            )
            deduct_stock(rx["medicine_id"], rx.get("quantity", 1))

        conn.commit()
    finally:
        conn.close()


def get_visits_for_patient(patient_id: int) -> list:
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT * FROM visits
               WHERE patient_id=? AND is_deleted=0
               ORDER BY visit_date DESC""",
            (patient_id,)
        ).fetchall()
    finally:
        conn.close()


def get_visit_by_id(visit_id: int) -> dict | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM visits WHERE id=?", (visit_id,)
        ).fetchone()
    finally:
        conn.close()


def get_prescriptions_for_visit(visit_id: int) -> list:
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT p.*, m.name AS medicine_name, m.unit
               FROM prescriptions p
               JOIN medicines m ON m.id = p.medicine_id
               WHERE p.visit_id=?""",
            (visit_id,)
        ).fetchall()
    finally:
        conn.close()


def update_visit(visit_id: int, symptoms: str, diagnosis: str, notes: str):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE visits SET symptoms=?, diagnosis=?, notes=?
               WHERE id=?""",
            (symptoms, diagnosis, notes, visit_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_visit(visit_id: int):
    soft_delete("visits", visit_id)
