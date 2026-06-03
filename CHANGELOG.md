# Changelog

## 2026-06-03

- Split the unauthenticated login page from the authenticated business app shell to prevent the workspace from flashing before login.
- Added server-side route checks so unauthenticated business routes redirect to `/login` while authenticated users can enter `/app`.
- Fixed authenticated `/app.js` routing so the business app receives JavaScript instead of the app shell HTML.
- Added `/api/me` as a current-user alias and switched login/app fetch calls to include credentials for consistent session initialization.

## 2026-06-02

- Added `scripts/import_formula_templates.py` to bulk import reusable formula templates from JSON.
- Added a sample import file at `examples/formula_templates.sample.json` and documented skip/update behavior for same-name templates.
- Cleaned up the `import_template_verify_20260602` verification customer and customer formula after a pre-deletion SQLite backup.
- Confirmed the two sample formula templates remain available after the import verification cleanup.
- Split the global formula library into a dedicated `formula_templates` table and moved customer case formula import to the new template source.
- Kept the old `formulas` table as a legacy tea package/export table instead of using the hidden `formula_library_client` compatibility path.
- Added safe migration logic that copies legacy formula library records into `formula_templates` without deleting legacy data.
- Cleaned up the confirmed formula library structure verification data after a pre-deletion SQLite backup.
- Verified `PRAGMA integrity_check=ok` and confirmed the business API remains normal after the formula library cleanup.
- Removed the legacy hidden compatibility client `formula_library_client` after confirming the system no longer depends on it.
- Verified database and API client counts are both zero after removing the hidden compatibility client.
- Enhanced the formula library with category, pattern, audience, composition, default dosage, modification rules, taste notes, cost notes, and internal notes.
- Added formula library management fields to the existing formula page while keeping old formula records compatible through safe SQLite column migrations.
- Updated customer case center formula import so library formulas can populate composition, dosage, usage, modification rules, cautions, and notes.
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
