# Changelog

## 2026-06-01

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
