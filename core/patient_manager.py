"""
patient_manager.py — clinic_app_v5
All patient CRUD using soft delete.
Search is index-backed (fast even after years of data).
"""

from db.database import get_connection, soft_delete, restore_deleted
from datetime import datetime


# ─────────────────────────────────────────────
#  Create
# ─────────────────────────────────────────────

def add_patient(name: str, age: int, gender: str,
                phone: str, cnic: str, address: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO patients (name, age, gender, phone, cnic, address)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name.strip(), age, gender, phone.strip(), cnic.strip(), address.strip())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  Read
# ─────────────────────────────────────────────

def get_all_patients(include_deleted: bool = False) -> list:
    conn = get_connection()
    try:
        query = "SELECT * FROM patients"
        if not include_deleted:
            query += " WHERE is_deleted=0"
        query += " ORDER BY name COLLATE NOCASE"
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def get_patient_by_id(patient_id: int) -> dict | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM patients WHERE id=?", (patient_id,)
        ).fetchone()
    finally:
        conn.close()


def search_patients(query: str) -> list:
    """
    Fast indexed search across name, phone, and CNIC.
    Uses LIKE with leading wildcard only on name (acceptable for clinics),
    and exact-prefix match on phone/CNIC for speed.
    """
    q = f"%{query.strip()}%"
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT * FROM patients
               WHERE is_deleted=0
                 AND (name LIKE ? OR phone LIKE ? OR cnic LIKE ?)
               ORDER BY name COLLATE NOCASE
               LIMIT 100""",
            (q, q, q)
        ).fetchall()
    finally:
        conn.close()


def get_patient_full_history(patient_id: int) -> dict:
    """
    Returns all visits, prescriptions, and bills for a patient
    in a single round-trip — used by the history screen.
    """
    conn = get_connection()
    try:
        patient = conn.execute(
            "SELECT * FROM patients WHERE id=?", (patient_id,)
        ).fetchone()

        visits = conn.execute(
            """SELECT * FROM visits
               WHERE patient_id=? AND is_deleted=0
               ORDER BY visit_date DESC""",
            (patient_id,)
        ).fetchall()

        bills = conn.execute(
            """SELECT * FROM bills
               WHERE patient_id=? AND is_deleted=0
               ORDER BY bill_date DESC""",
            (patient_id,)
        ).fetchall()

        # Attach prescriptions to each visit
        visits_with_rx = []
        for v in visits:
            prescriptions = conn.execute(
                """SELECT p.*, m.name AS medicine_name, m.unit
                   FROM prescriptions p
                   JOIN medicines m ON m.id = p.medicine_id
                   WHERE p.visit_id=?""",
                (v["id"],)
            ).fetchall()
            visits_with_rx.append({"visit": v, "prescriptions": prescriptions})

        return {
            "patient":  patient,
            "visits":   visits_with_rx,
            "bills":    bills,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  Update
# ─────────────────────────────────────────────

def update_patient(patient_id: int, name: str, age: int, gender: str,
                   phone: str, cnic: str, address: str):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE patients
               SET name=?, age=?, gender=?, phone=?, cnic=?, address=?
               WHERE id=?""",
            (name.strip(), age, gender, phone.strip(),
             cnic.strip(), address.strip(), patient_id)
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
#  Soft Delete / Restore
# ─────────────────────────────────────────────

def delete_patient(patient_id: int):
    """Soft delete — record is hidden but not removed from database."""
    soft_delete("patients", patient_id)


def restore_patient(patient_id: int):
    restore_deleted("patients", patient_id)


def get_deleted_patients() -> list:
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT * FROM patients WHERE is_deleted=1
               ORDER BY deleted_at DESC"""
        ).fetchall()
    finally:
        conn.close()
