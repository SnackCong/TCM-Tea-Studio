# Changelog

## 2026-06-01

- Added customer detail view with profile summary and creation time.
- Added follow-up/visit records linked to customers via `client_id`.
- Added visit fields: date, complaint change, sleep, diet, stool, tongue, pulse, advice, and notes.
- Added historical visit list sorted by visit date descending.
- Added the first practical customer profile workflow.
- Added `gender` to customer profiles with a safe SQLite migration.
- Updated the customer form to support name, gender, age, phone, main complaint, notes, and optional constitution classification.
- Updated customer list rendering and search to include gender and notes.
- Kept existing SQLite data compatible; existing customers without gender display as not filled.
