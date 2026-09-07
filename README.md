# Clinic App v5

## What Changed from v4

| Area | v4 | v5 |
|---|---|---|
| Database backup | None | Auto backup every startup (safe API) |
| Backup storage | — | `backups/` folder, last 30 copies kept |
| Soft delete | Hard delete (data lost forever) | Soft delete — records recoverable |
| Database indexes | None | Indexes on name, phone, CNIC, date |
| DB crash safety | Default mode | WAL mode (crash-safe) |
| Schema versioning | None | `schema_version` table tracks upgrades |
| Medicine stock | Not tracked | Stock qty + expiry date + alerts |
| Token queue | None | Daily patient queue with token numbers |
| PDF folder | All in one flat folder | Organised: `reports_output/YYYY/MM/` |
| Startup alerts | None | Low stock & expiry warnings on open |
| Config | Hardcoded | `clinic_config.json` — editable |
| Maintenance | Manual | `maintenance.py` script |

---

## Installation

```bash
pip install -r requirements.txt
python main.py
```

---

## File Structure

```
clinic_app_v5/
├── main.py                      ← Entry point
├── config.py                    ← Settings loader
├── clinic_config.json           ← Your clinic name, fees, etc. (auto-created)
├── maintenance.py               ← Run monthly
├── requirements.txt
│
├── db/
│   └── database.py              ← Connection, migrations, backup, VACUUM
│
├── core/
│   ├── patient_manager.py
│   ├── visit_manager.py
│   ├── medicine_manager.py      ← Now includes stock + expiry
│   ├── billing_manager.py       ← Now includes monthly summary
│   ├── appointment_manager.py   ← NEW: daily token queue
│   └── service_manager.py
│
├── ui/
│   ├── main_window.py
│   ├── dashboard.py
│   ├── patient_form.py
│   ├── billing_screen.py
│   ├── medicine_screen.py
│   ├── service_screen.py
│   └── search_screen.py
│
├── reports/
│   └── pdf_generator.py         ← Now saves to YYYY/MM subfolders
│
├── reports_output/              ← PDFs organised by year/month
│   └── 2026/
│       └── 04/
│           ├── bill_1_....pdf
│           └── prescription_1_....pdf
│
└── backups/                     ← Auto-created, 30 rolling copies
    ├── clinic_backup_2026-04-18_08-00.db
    └── ...
```

---

## Clinic Configuration

Edit `clinic_config.json` (or use the Settings screen):

```json
{
  "clinic_name": "Al-Shifa Clinic",
  "doctor_name": "Dr. Ahmed",
  "clinic_address": "Main Bazaar, Rahim Yar Khan",
  "clinic_phone": "0300-0000000",
  "default_consultation_fee": 500,
  "low_stock_threshold": 10,
  "expiry_alert_days": 30,
  "max_backups": 30
}
```

---

## Monthly Maintenance (5 minutes)

```bash
python maintenance.py
```

This checks database health, compacts it, and shows statistics.
Run it on the first day of every month.

---

## How to Restore from Backup

**Never overwrite the live database directly.**

1. Go to the `backups/` folder
2. Find the most recent `clinic_backup_YYYY-MM-DD_HH-MM.db`
3. Rename the current `db/clinic.db` to `db/clinic_BROKEN.db`
4. Copy your chosen backup to `db/clinic.db`
5. Open the app and verify patients/bills appear correctly
6. Once confirmed, delete `clinic_BROKEN.db`

---

## How to Upgrade to a New Computer

1. Copy the entire `clinic_app_v5/` folder to the new computer
2. Install Python 3.12 and run `pip install -r requirements.txt`
3. Run `python main.py`

The database (`db/clinic.db`) travels with the folder — all data intact.

---

## Annual Tasks

- [ ] Run `maintenance.py` and check output
- [ ] Copy latest backup to an external USB drive
- [ ] Check hard drive health (use CrystalDiskInfo on Windows)
- [ ] Confirm backup restore works on a test copy
- [ ] Archive `reports_output/YYYY/` for the past year to external drive
