# LEXSECURE — API Reference

Every endpoint is under `/api`. Authentication is a bearer JWT:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/documents
```

Generated from the live OpenAPI schema (`/openapi.json`).

## Authentication & MFA

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/api/auth/login` | Login | user |
| `POST` | `/api/auth/logout` | Logout | user |
| `GET` | `/api/auth/me` | Get Current User Profile | user |
| `POST` | `/api/auth/mfa/activate` | Mfa Activate | user |
| `POST` | `/api/auth/mfa/backup-codes` | Mfa Backup Codes | user |
| `POST` | `/api/auth/mfa/disable` | Mfa Disable | user |
| `POST` | `/api/auth/mfa/setup` | Mfa Setup | user |
| `GET` | `/api/auth/mfa/status` | Mfa Status | user |

## Cases

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/cases` | List Cases | user |
| `POST` | `/api/cases` | Create Case | user |
| `GET` | `/api/cases/{case_id}` | Get Case Details | user |
| `GET` | `/api/cases/{case_id}/documents` | Get Case Documents | user |

## Documents

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/documents` | List Documents | user |
| `POST` | `/api/documents/upload` | Upload Document | user |
| `GET` | `/api/documents/{document_id}` | Get Document Details | user |
| `GET` | `/api/documents/{document_id}/download` | Download Document | user |
| `PATCH` | `/api/documents/{document_id}/dual-auth` | Set Dual Auth | user |
| `DELETE` | `/api/documents/{document_id}/sign` | Unsign Document | user |
| `POST` | `/api/documents/{document_id}/sign` | Sign Document | user |
| `POST` | `/api/documents/{document_id}/versions` | Create New Version | user |

## Two-Man Rule Approvals

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/approvals/my-requests` | Get My Requests | user |
| `GET` | `/api/approvals/pending` | Get Pending Requests | user |
| `POST` | `/api/approvals/process` | Process Request | user |
| `POST` | `/api/approvals/request` | Request Access | user |

## Collaboration & Workflow

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/api/workflow/approve` | Approve Document | user |
| `POST` | `/api/workflow/comments` | Add Document Comment | user |
| `GET` | `/api/workflow/comments/{document_id}` | Get Document Comments | user |
| `POST` | `/api/workflow/reject` | Reject Document | user |
| `GET` | `/api/workflow/tasks` | Get Pending Tasks | user |

## Integrity & Ledger

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/api/integrity/extract-watermark` | Extract Watermark Endpoint | user |
| `GET` | `/api/integrity/ledger` | Get Ledger Blocks | user |
| `GET` | `/api/integrity/monitor` | Integrity Monitor State | user |
| `POST` | `/api/integrity/restore/{version_id}` | Restore Tampered Document | user |
| `POST` | `/api/integrity/sweep` | Run Integrity Sweep Now | user |
| `POST` | `/api/integrity/tamper-test/{version_id}` | Execute Tamper Test | user |
| `GET` | `/api/integrity/verify-chain` | Verify Blockchain Chain | user |
| `POST` | `/api/integrity/verify/{version_id}` | Verify Document | user |

## AI & Vector Search

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/api/ai/ask` | Ask Ai Assistant | user |
| `POST` | `/api/ai/search` | Semantic Search | user |
| `GET` | `/api/ai/status` | Get Ai Status | user |
| `GET` | `/api/ai/suggested-prompts` | Get Suggested Prompts | user |

## Audit & Compliance

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/audit` | List Audit Logs | user |
| `GET` | `/api/audit/document/{document_id}` | Get Document Audit Trail | user |
| `GET` | `/api/audit/export` | Export Audit Logs | user |

## Court Packages

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/reports/court-package/{case_id}` | Generate Court Submission Package | user |

## Administration

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/admin/policies` | Get Access Policies | admin |
| `GET` | `/api/admin/system-health` | Get System Health | admin |
| `GET` | `/api/admin/users` | List System Users | admin |

## Other

| Method | Path |
|---|---|
| `GET` | `/` |
| `GET` | `/health` |

## Status codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `401` | Missing, invalid, expired or revoked token |
| `403` | Authenticated but not permitted (RBAC role or ABAC assignment) |
| `404` | Not found, or deliberately hidden by an ABAC check |
| `409` | Conflict — e.g. a tampered payload that cannot be decrypted |
| `422` | Validation error |
| `429` | Login rate limit tripped |
| `4401` | WebSocket rejected — invalid or expired token |

## Related documents

- [Getting Started](GETTING_STARTED.md) — install, sign in, first steps
- [App Tour](APP_TOUR.md) — every screen, with screenshots
- [UI Reference](UI_REFERENCE.md) — every control explained
- [Architecture Guide](ARCHITECTURE.md) — how it works underneath
- [API Reference](API.md) — this document
