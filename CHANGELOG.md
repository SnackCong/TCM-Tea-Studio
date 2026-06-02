# Changelog

## 2026-06-02

- Turned the customer detail page into a customer case center with a combined timeline for follow-up records and tea formula records.
- Added client todo records with reminder date, completion status, and notes using a safe `client_todos` table migration.
- Added copy-as-new support for historical client tea formulas.
- Added a formula library call-in flow that reuses existing tea package formulas as draft client tea formulas.
- Cleaned up the `case_center_verify_20260602` deployment verification data after a pre-deletion SQLite backup.
- Verified `PRAGMA integrity_check=ok` and confirmed the authenticated business API remains normal after the cleanup.
- Deleted the previously listed deployment verification test customers, follow-up records, and tea formula records after explicit confirmation.
- Created a pre-deletion SQLite backup and verified `PRAGMA integrity_check=ok` after deletion.
- Verified anonymous API access still returns `401` and authenticated business data API access remains normal.

## 2026-06-01

- Added `Secure` to the session cookie by default while preserving `HttpOnly` and `SameSite=Lax`.
- Documented post-launch test data deletion plan and current authentication risk notes.
- Added customer-linked tea formula/treatment plan records via `client_formulas`.
- Added optional association between a tea formula and a follow-up record.
- Added tea formula fields for date, formula name, herbs, dosages, preparation method, period, modifications, cautions, and notes.
- Added historical tea formula list on the customer detail page, sorted by date descending.
- Added customer detail view with profile summary and creation time.
- Added follow-up/visit records linked to customers via `client_id`.
- Added visit fields: date, complaint change, sleep, diet, stool, tongue, pulse, advice, and notes.
- Added historical visit list sorted by visit date descending.
- Added the first practical customer profile workflow.
- Added `gender` to customer profiles with a safe SQLite migration.
- Updated the customer form to support name, gender, age, phone, main complaint, notes, and optional constitution classification.
- Updated customer list rendering and search to include gender and notes.
- Kept existing SQLite data compatible; existing customers without gender display as not filled.
