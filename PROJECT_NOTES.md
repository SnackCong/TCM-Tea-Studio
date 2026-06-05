# TCM-Tea-Studio — PROJECT_NOTES.md

## Project Overview

TCM-Tea-Studio is a lightweight management platform for traditional Chinese medicine (TCM) tea formulations and health conditioning records.

The project is intended for:
- Customer health record management
- Tea formula management
- Syndrome differentiation support
- Case library accumulation
- Future AI-assisted TCM analysis

The long-term goal is to build a professional, lightweight, privacy-friendly TCM conditioning workstation.

---

# Current Project Status

Current phase:
- Early MVP stage
- Core login/authentication system completed
- VPS deployment completed
- Domain accessible online
- Frontend and backend basic architecture established

Current production domain:
https://congnet.xyz/

---

# Tech Stack

## Frontend
- Vanilla HTML/CSS/JavaScript served by the Python app

## Backend
- Python standard library HTTP server

## Database
- SQLite

## Deployment
- Debian 12 VPS
- systemd service `tcm-tea-studio`
- Host Nginx for HTTPS and Docker `mynginx` for HTTP reverse proxy

## Version Control
- Git
- GitHub

---

# Important Architecture Notes

## Authentication System

Current authentication method:
- Session + Cookie based authentication

Rules:
- Session expires after 30 minutes
- Backend validates session expiration
- Logout must:
  - delete session from database
  - clear cookie on frontend and backend

Security requirements:
- Unauthenticated users cannot access /app
- Frontend must not rely only on localStorage authentication state
- Backend authentication validation is mandatory
- Real passwords must never be written into code, logs, documentation, test fixtures, or commits

## Account Security

Implemented account security functions:
- Authenticated admins can change their password from the `/app` account security view.
- Password changes require the current password even when the user is already logged in.
- New password validation requires a non-empty value, at least 8 characters, matching confirmation, and a value different from the current password.
- Passwords continue to use the existing PBKDF2-SHA256 hash storage and are never stored in plaintext.
- After a successful password change, all sessions for that user are deleted, the session cookie is cleared, and the browser returns to the login page.
- Do not document, log, commit, or paste real admin passwords into the repository.

## /app Session Expiry Reauthentication

Design decision:
- Once the authenticated app shell has loaded, normal business editing flows must not redirect directly to `/login` when the session expires.
- Customer profile, follow-up, client tea formula, formula template, and todo saves must call `requireAuthOrReauth()` before sending the save request.
- If the browser cookie has expired or the in-memory user state is missing, the app shows the local re-login modal and preserves the current DOM form values.
- After `/api/login` succeeds, the app must call `/api/me` or `/api/session` to confirm the admin session before continuing.
- The failed request may be retried automatically. If retry cannot be completed safely, the page must keep the form data and tell the user to click save again.
- Only explicit logout, first unauthenticated page access, or user cancellation of re-login may navigate to the full login page.
- Do not clear form state, reset the app, or call `showLogin()` from ordinary `/app` save flows.

Safe verification:
- Use `scripts/expire_session.py --token <controlled-token> --confirm EXPIRE_SESSION` with `TCM_DB_PATH` pointing at the target database.
- Do not add a public HTTP endpoint for expiring sessions.

## Customer Profile Form Mode Visibility

UX decision:
- The customer profile form uses one left-side form for both creating and editing customers.
- The form must display a visible mode banner so the user can always tell whether they are creating a new customer or editing an existing customer.
- New mode shows `新建客户档案`.
- Edit mode shows `正在编辑客户：<客户姓名>` plus created/updated timestamps when available.
- `+ 新建客户` and `取消编辑` both clear the form and return it to new mode.
- This avoids accidental modification of an existing customer after leaving the page open for minutes or hours.

## Formula Template Form Structure

UX and data-entry decision:
- The formula library form uses one left-side form for both creating and editing formula templates.
- The form must display a visible mode banner so the user can always tell whether they are creating a new template or editing an existing template.
- New mode shows `新建配方模板`.
- Edit mode shows `正在编辑配方：<方名>` plus created/updated timestamps when available.
- `+ 新建配方` and `取消编辑` both clear the form and return it to new mode.
- Formula template composition is entered through structured ingredient rows instead of separate free-text composition and dosage fields.
- The structured rows generate the existing `composition` field as ingredient names joined by `、` and `default_dosage` as `药名剂量g` entries joined by `，`.
- Each structured ingredient row should remain horizontally aligned on desktop: herb name, dosage, fixed `g` unit, and delete control. Mobile layouts may tighten or wrap when space is constrained.
- Ingredient rows use fixed alignment columns for herb name, dosage, and unit, with the delete control pushed toward the available right-side space for clearer scanning and safer clicking.
- The formula library records package count, single-package grams, and total grams for quick template-level dosing estimates.
- The previous duplicate ingredient module on the formula library page was removed; formula template entry should use only the structured composition rows.
- When existing `default_dosage` text can be parsed, the edit form reconstructs structured rows. If parsing fails, the UI keeps the old text visible in a warning and requires manual cleanup before saving.

---

# Deployment Notes

## VPS Deployment Path

Production path:
/opt/tcm-tea-studio

## Backup Path

/root/tcm-tea-studio-backups/

SQLite backups are created before deployment.

## Deployment Script

Use:
deploy_safe.sh

Requirements:
- Automatically backup SQLite before deployment
- Restart only `tcm-tea-studio` after deployment
- Prevent accidental overwrite of database

---

# Current Features

Completed:
- Login page
- Session authentication
- Logout functionality
- Cookie clearing
- In-app re-login modal for expired sessions
- Route protection
- Backend auth validation
- Customer profiles
- Customer case center
- Follow-up records
- Client tea formula records
- Formula templates and JSON import
- Client todos
- VPS deployment
- Domain access
- GitHub repository sync

Planned:
- Customer management
- Tea formula templates
- Health record system
- Case library
- Search functionality
- PDF export
- Mobile adaptation
- AI-assisted syndrome differentiation
- Multi-user support

---

# Database Notes

Current database:
- SQLite

Important rules:
- Never overwrite production database directly
- Always backup before migrations
- Keep compatibility with existing tables

Future possible upgrade:
- PostgreSQL

---

# AI Assistant Rules

IMPORTANT:
Any AI assistant (Codex / ChatGPT / other agents) must follow these rules.

## Before Modifying Code

Always:
1. Read PROJECT_NOTES.md
2. Read README.md
3. Check recent git commits
4. Understand current authentication logic
5. Understand deployment workflow

---

## Deployment Safety Rules

Before deployment:
- Backup SQLite database
- Verify environment variables
- Ensure PM2 restart succeeds
- Ensure login system still works

After deployment verify:
- /login works
- /api/me works
- /api/data works
- logout works
- unauthenticated access redirects correctly
- /app session-expiry re-login modal preserves unsaved form input

---

## Authentication Safety Rules

DO NOT:
- Replace session authentication casually
- Remove backend auth validation
- Store sensitive auth state only in frontend
- Break cookie clearing behavior
- Redirect from ordinary /app business save flows to the full login page on session expiry
- Clear unsaved form input during local reauthentication
- Write real passwords into code, logs, docs, tests, commits, or deployment notes

---

## Database Safety Rules

DO NOT:
- Delete production tables casually
- Reset SQLite database
- Change schema without migration plan

Always:
- Backup before database operations

---

# Git Workflow

Recommended workflow:
- One feature = one commit
- Stable milestones should use tags

Suggested version examples:
- v0.1.0
- v0.2.0
- v1.0.0

---

# Suggested Folder Structure

project-root/
├── PROJECT_NOTES.md
├── README.md
├── DEPLOY.md
├── CHANGELOG.md
├── frontend/
├── backend/
├── scripts/
└── backups/

---

# Current TODO

## High Priority
- Customer profile system
- Tea formula management
- Case library system
- Search and filtering
- Better UI polish

## Medium Priority
- PDF export
- Data statistics
- Mobile responsive UI
- Role permissions

## Long-term Ideas
- AI-assisted TCM syndrome analysis
- Intelligent tea recommendation
- Follow-up reminder system
- WeChat ecosystem integration

---

# Development Philosophy

Project principles:
- Lightweight
- Stable
- Privacy-first
- Easy deployment
- Easy maintenance
- AI-collaboration friendly

The project should remain understandable and maintainable for a solo developer assisted by AI coding tools.

---

# Notes For Future Development

Important:
This project is being developed incrementally with AI assistance.

Maintain:
- clear structure
- readable code
- safe deployment process
- minimal unnecessary complexity

Prefer:
- simplicity over over-engineering
- maintainability over cleverness
- stability over rapid refactoring

---

# Maintainer

Primary maintainer:
Snack Cong

Project:
TCM-Tea-Studio
