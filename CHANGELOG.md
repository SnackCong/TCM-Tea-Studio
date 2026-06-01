# Changelog

## 2026-06-01

- Added the first practical customer profile workflow.
- Added `gender` to customer profiles with a safe SQLite migration.
- Updated the customer form to support name, gender, age, phone, main complaint, notes, and optional constitution classification.
- Updated customer list rendering and search to include gender and notes.
- Kept existing SQLite data compatible; existing customers without gender display as not filled.
