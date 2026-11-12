# LEXSECURE — Architecture Guide

See also the [App Tour](APP_TOUR.md) for a screen-by-screen walkthrough and the
[API Reference](API.md) for the full endpoint list.

## Stack
- Backend: FastAPI + SQLAlchemy 2 + **PostgreSQL 16** (SQLite fallback) + AES-256-GCM + RSA-PSS 2048 + SHA-256 + append-only hash-chain ledger + local dense vectors + RAG.
- Frontend: React + Vite + Tailwind + Axios + React Router.
- Auth: bcrypt + JWT (8h) + real TOTP (RFC 6238) with one-time backup codes and DB-backed lockout.
- Uploads: ClamAV when installed, plus a structural heuristic engine (EICAR, disguised executables, PDF active content, Office macros, archive bombs, double extensions).
- Operations: continuous integrity monitor, live WebSocket feed, audit export with SHA-256 attestation.

## Security pipeline (upload)
Malware scan → text extract/OCR → AI classify → SHA-256 → RSA-PSS sign → AES-256-GCM encrypt → vault/MinIO store → Document + Version + Metadata (scan engine/verdict) + Signature rows → ledger block → vector chunks → audit log.

## ABAC model
- `CaseAssignment(case_id, user_id)` gates all document/case/AI access.
- Supervisor/Admin see all audit logs; others see only their own.
- AI search filters `authorized_case_ids` BEFORE vector ranking.
- Workflow approvals and rejections are ABAC-checked too — a Legal Officer cannot approve a document in a case they are not assigned to.

## Custody ledger
Each block stores `previous_hash` and `block_hash = SHA-256(block fields)`. The
genesis block anchors the chain with 64 zeros. Block numbers are allocated
under a lock so concurrent writes cannot fork the chain, and
`verify_ledger_chain_integrity()` recomputes every hash from the stored fields
rather than trusting a cached flag.

## Key APIs
- `POST /api/auth/login` — password + TOTP (or a single-use backup code)
- `POST /api/auth/mfa/setup|activate|disable|backup-codes` — authenticator lifecycle
- `GET  /api/auth/mfa/status`, `GET /api/auth/me`, `POST /api/auth/logout`
- `GET/POST /api/cases`, `GET /api/cases/{id}`, `GET /api/cases/{id}/documents`
- `GET /api/documents`, `POST /api/documents/upload`, `GET /api/documents/{id}`, `POST /api/documents/{id}/versions`, `POST /api/documents/{id}/sign`, `GET /api/documents/{id}/download`
- `PATCH /api/documents/{id}/dual-auth` — seal or unseal under the Two-Man Rule
- `POST /api/approvals/request|process`, `GET /api/approvals/pending|my-requests`
- `POST /api/integrity/verify/{version_id}`, `POST /api/integrity/tamper-test/{version_id}` (drill, supervisor/admin), `POST /api/integrity/restore/{version_id}`
- `GET  /api/integrity/ledger`, `GET /api/integrity/verify-chain`, `GET /api/integrity/monitor`, `POST /api/integrity/sweep`
- `POST /api/integrity/extract-watermark` — leak attribution (supervisor/admin)
- `POST /api/ai/search`, `POST /api/ai/ask`, `GET /api/ai/status`
- `POST /api/workflow/approve|reject`, `GET/POST /api/workflow/comments`, `GET /api/workflow/tasks`
- `GET  /api/audit`, `GET /api/audit/document/{id}`, `GET /api/audit/export?format=csv|json`
- `GET  /api/reports/court-package/{case_id}` (Sec 65B/BSA manifest)
- `GET  /api/admin/users|system-health|policies`

## Run / verify
1. `./start.sh` (starts PostgreSQL if the bundled Postgres.app cluster exists, then API + UI).
2. Enrol authenticators: `cd backend && source venv/bin/activate && python scripts/provision_mfa.py`.
3. Login as investigator at `http://localhost:5173` with the 6-digit TOTP code.
4. Documents → open a document → Verify Integrity. Supervisors/Admins can run an integrity drill.
5. AI Search "financial fraud" as investigator (no results) vs supervisor (results) — ABAC applies before retrieval.
6. Cases → open CASE-2026-002 as investigator → 403; as supervisor → allowed.
7. Court package from case detail → download JSON manifest.
8. Admin → System Health shows the live database engine, scanner, ledger chain and integrity monitor.
