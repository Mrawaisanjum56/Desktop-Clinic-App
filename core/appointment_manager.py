"""
appointment_manager.py — clinic_app_v5 (NEW)
Daily token queue management.
Assigns auto-incrementing token numbers per day.
"""

from db.database import get_connection
from datetime import datetime, date


def add_appointment(patient_id: int,
                    appt_date: str = None,
                    notes: str = "") -> int:
    """
    Add patient to today's queue. Token number is auto-assigned
    as (max token for that day) + 1.
    """
    if appt_date is None:
        appt_date = date.today().isoformat()

    conn = get_connection()
    try:
        # Get next token number for this date
        max_token = conn.execute(
            "SELECT COALESCE(MAX(token_no), 0) FROM appointments WHERE appt_date=?",
            (appt_date,)
        ).fetchone()[0]
        token = max_token + 1

        cur = conn.execute(
            """INSERT INTO appointments
                   (patient_id, appt_date, token_no, status, notes)
               VALUES (?, ?, ?, 'waiting', ?)""",
            (patient_id, appt_date, token, notes)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_queue_for_date(appt_date: str = None) -> list:
    """Returns all appointments for a date, ordered by token number."""
    if appt_date is None:
        appt_date = date.today().isoformat()

    conn = get_connection()
    try:
        return conn.execute(
            """SELECT a.*, p.name AS patient_name, p.phone
               FROM appointments a
               JOIN patients p ON p.id = a.patient_id
               WHERE a.appt_date=?
               ORDER BY a.token_no ASC""",
            (appt_date,)
        ).fetchall()
    finally:
        conn.close()


def update_status(appointment_id: int,
                  status: str):
    """status: 'waiting' | 'in-progress' | 'done' | 'cancelled'"""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE appointments SET status=? WHERE id=?",
            (status, appointment_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_next_waiting(appt_date: str = None) -> dict | None:
    """Returns the next patient still waiting (lowest token, status='waiting')."""
    if appt_date is None:
        appt_date = date.today().isoformat()

    conn = get_connection()
    try:
        return conn.execute(
            """SELECT a.*, p.name AS patient_name
               FROM appointments a
               JOIN patients p ON p.id = a.patient_id
               WHERE a.appt_date=? AND a.status='waiting'
               ORDER BY a.token_no ASC
               LIMIT 1""",
            (appt_date,)
        ).fetchone()
    finally:
        conn.close()


def cancel_appointment(appointment_id: int):
    update_status(appointment_id, "cancelled")


def get_today_stats() -> dict:
    today = date.today().isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT status, COUNT(*) AS cnt
               FROM appointments WHERE appt_date=?
               GROUP BY status""",
            (today,)
        ).fetchall()
        stats = {"waiting": 0, "in-progress": 0, "done": 0, "cancelled": 0}
        for r in rows:
            stats[r["status"]] = r["cnt"]
        stats["total"] = sum(stats.values())
        return stats
    finally:
        conn.close()
