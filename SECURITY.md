# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 2.x (current) | ✅ |
| < 2.0 | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.** A public
issue exposes the problem to everyone before it is fixed.

Report it privately instead:

1. Use **GitHub's "Report a vulnerability"** button on the Security tab of the
   repository (Settings → Security → Report a vulnerability). This opens a
   private advisory visible only to the maintainer.
2. If that is unavailable, open an issue titled **`[SECURITY]`** and mark it
   as a draft for the first few minutes so it is not immediately visible.

Please include:

- What the issue is and which part of the system it affects
- Steps to reproduce, and the exact version or commit
- The impact — what an attacker could achieve
- Any proof-of-concept code or screenshots
- Whether the issue is already public anywhere

## What to expect

| Stage | Target |
|---|---|
| Acknowledgement | Within 72 hours |
| Initial assessment (severity, scope) | Within 7 days |
| Fix or mitigation plan | Depends on severity |
| Disclosure | After a fix is released, or coordinated with you |

You will be credited in the release notes unless you prefer otherwise.

## Scope

In scope:

- Authentication, session handling, MFA enrolment and recovery
- The ABAC / RBAC policy engine — any path to a document or case you should not reach
- Token issuance, validation and revocation
- The encryption, hashing and signature code paths
- The custody ledger and its verification
- The upload pipeline, including the malware scanner
- The steganographic leak tracker — where the watermark is applied and how it is read
- The audit trail, including the export attestation
- The AI provider adapters — chiefly, whether unauthorized content can reach a model

Out of scope:

- Findings that require an already-compromised host
- Denial of service through deliberate resource exhaustion of the LLM provider
- Missing hardening headers on a development-only server
- The bundled sample data and demo accounts, which are public by design
- Social engineering of a human operator

## Hardening notes for operators

The defaults are development defaults. Before running this anywhere real:

```bash
# Strong, unique secrets — the app refuses to start in production without them
JWT_SECRET_KEY=$(openssl rand -hex 32)
DOCUMENT_ENCRYPTION_KEY=$(openssl rand -hex 32)

# Set ENVIRONMENT=production to enable the startup guard
```

The application refuses to start with `ENVIRONMENT=production` while either
secret still holds its placeholder value. The demo accounts in the README have
no second factor and are administrator accounts — delete them before any real
deployment:

```bash
cd backend && venv/bin/python -c "
import os, sys; sys.path.insert(0, '.')
from app.database.session import SessionLocal
from app.models.user import User
db = SessionLocal()
for u in db.query(User).filter(User.email.like('demo%')).all():
    db.delete(u)
db.commit()
"
```

Enable TLS termination in front of the API, and keep the encrypted vault
directory on encrypted storage.
