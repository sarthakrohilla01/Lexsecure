# LEXSECURE Documentation

| Document | What it covers | Read it if… |
|---|---|---|
| **[GETTING_STARTED.md](GETTING_STARTED.md)** | Install, sign in, every account, first 5 minutes, troubleshooting, glossary | You have **never seen this project** |
| **[APP_TOUR.md](APP_TOUR.md)** | Guided walkthrough of all 12 screens with screenshots | You want to **see what it does** |
| **[UI_REFERENCE.md](UI_REFERENCE.md)** | Every button, badge, field and panel explained | You want to know **what each control means** |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Stack, upload pipeline, ABAC model, custody ledger, endpoints | You want to know **how it works** |
| **[API.md](API.md)** | Endpoint reference with auth requirements and status codes | You want to **call it programmatically** |

## Read it in the app

The same material is built into the application as a **Guide** section in the
left sidebar, and `/guide` opens without a session — so a first-time visitor
can read it before authenticating.

## The short version

LEXSECURE is a document management system for investigative teams where the
point is not the storage — it is the **proof**. Every file is hashed, signed,
encrypted and appended to a tamper-evident chain, and every access is written
to an immutable audit trail.

Three ideas hold the whole thing together:

**1. Authorization is a filter, not a check.**
Case assignment (`CaseAssignment`) decides what exists for you. The AI never
receives a chunk you cannot open, because the ABAC filter runs *before*
ranking, not after. An Investigator genuinely cannot see a case they are not
assigned to — the API answers 403 and the frontend renders an explicit
"Access Restricted" panel, not an empty list.

**2. Integrity is checked against three independent anchors.**
The decrypted bytes must hash to the stored SHA-256, the RSA-PSS signature
must verify against that digest, and the ledger block for that version must
still match. One anchor can be fooled; three at once are much harder.

**3. Nothing claims more than it did.**
If the LLM provider is down, the app answers from a deterministic template and
says so. If a scan finds no watermark, the leak investigator reports "no
verifiable watermark" instead of guessing. The AI badge names the provider and
model that actually produced the text.

## Running it

```bash
./start.sh                                    # backend :8000 + frontend :5173
cd backend && venv/bin/python seed.py         # sample cases and evidence
cd backend && venv/bin/python scripts/create_demo_accounts.py
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite file | PostgreSQL 16 in production |
| `JWT_SECRET_KEY` | dev placeholder | Refuses to boot in production if unchanged |
| `DOCUMENT_ENCRYPTION_KEY` | dev placeholder | 64 hex chars = 32 bytes for AES-256 |
| `LLM_PROVIDER` | `none` | `nara`, `gemini`, `ollama`, `openai` |
| `NARA_API_KEY` | empty | NaraRouter key (`sk-nry-…`) |
| `LLM_MODEL` | `agnes-2.5-flash` | Only model on the NaraRouter free plan |
| `STORAGE_TYPE` | `vault` | `vault` or `minio` |
| `INTEGRITY_CHECK_INTERVAL_SECONDS` | `300` | `0` disables the background sweep |
| `MFA_TOTP_WINDOW` | `1` | ±1 step of clock drift |

Full list with comments: [`backend/.env.example`](../backend/.env.example).

## Contributing and licensing

The project is licensed under the [Business Source License 1.1](../LICENSE):
non-production use is granted outright; production use or redistribution
requires the work to come back to the canonical repository.

- [CONTRIBUTING.md](../CONTRIBUTING.md) — how to contribute, and what gets reviewed
- [SECURITY.md](../SECURITY.md) — reporting a vulnerability privately
- [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) — participation terms
- [CHANGELOG.md](../CHANGELOG.md) — release history

## Where things live

```
backend/app/
  api/           HTTP routes — one module per domain
  models/        SQLAlchemy tables
  schemas/       Pydantic request/response models
  security/      JWT, MFA, crypto, PKI, ABAC
  services/      ingestion, tampering, malware, OCR, steganography
  ai/            embeddings, vector store, RAG engine, LLM adapters
  blockchain/    append-only hash chain + adapter interface
  storage/       local encrypted vault, MinIO adapter
  audit/         immutable event log

frontend/src/
  pages/         one component per route
  components/    shared UI
  context/       auth state
  api/           axios client, WebSocket feed
  hooks/         useSecurityFeed
  layouts/       app shell
```

## Security posture

| Control | Implementation |
|---|---|
| Passwords | bcrypt |
| Second factor | TOTP (RFC 6238), replay protected, single-use backup codes |
| Brute force | Database-backed lockout, 10 failures / 5 min per IP + account |
| Sessions | 8-hour JWT, server-side revocation on logout |
| At rest | AES-256-GCM, 12-byte random IV per object |
| Signing | RSA-PSS 2048 over the SHA-256 digest; private key encrypted at rest |
| Chain of custody | Append-only SHA-256 hash chain, genesis-anchored |
| Upload scanning | ClamAV when installed + structural heuristics |
| Leak tracing | Zero-width steganographic watermark on text downloads |
| Headers | `nosniff`, `DENY` framing, `no-referrer`, restrictive permissions policy |
| CORS | Locked to local dev origins, no wildcard |

## Tests

```bash
cd backend && venv/bin/python -m pytest tests/ -q
```

41 tests covering the upload pipeline, the custody chain, TOTP replay
protection, the two-man rule, the leak tracker, ABAC scoping, audit export
attestation, login rate limiting and the security headers.
