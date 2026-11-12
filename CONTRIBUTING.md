# Contributing to LEXSECURE

Thanks for wanting to help. This document is the practical side of the
[Business Source License 1.1](LICENSE) — it explains what you need to do to
use LEXSECURE and how to contribute back.

## The short version

**Do not fork to publish a divergent copy. Open a pull request against this
repository instead.**

The license grants a limited right to use the code. For that right to include
production use or redistribution, the work has to come back here. In practice:

| You want to… | Do this |
|---|---|
| Report a bug | Open an issue |
| Fix a bug or add a feature | Fork → branch → pull request (the fork is just a workspace) |
| Use LEXSECURE internally, unmodified | Fine — non-production use is granted |
| Use LEXSECURE in production, or ship a modified copy | Pull request first, or ask for a commercial license |
| Study the code, learn from it, write about it | Fine |

A pull request is always credited to you, and your contribution stays in the
project's history. That is the whole point.

## Why this way

The code implements a legal-evidence chain: hashes, signatures, a custody
ledger. If two divergent copies existed, an "official" one would be
meaningless — which half is the record of truth? Keeping one canonical
repository with visible history is part of the design, not just the licence.

## How to contribute

### 1. Set up

```bash
git clone https://github.com/lexsecure/lexsecure
cd lexsecure
cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt && cd ..
cd frontend && npm install && cd ..
```

PostgreSQL 16 is expected in development. `docker-compose.yml` provides one,
and `./start.sh` starts a bundled local cluster if you have Postgres.app
installed.

```bash
./start.sh
cd backend && venv/bin/python seed.py && venv/bin/python scripts/create_demo_accounts.py
```

### 2. Branch

```bash
git checkout -b feature/short-descriptive-name
```

### 3. Make the change

Keep it focused — one concern per pull request. Match the surrounding style:
the Python is plain and dependency-light, the TypeScript is typed React with
Tailwind.

### 4. Check it

```bash
cd backend && venv/bin/python -m pytest tests/ -q
cd frontend && npm run build
```

CI runs the same two commands on every push, plus a licence and import check.
Both must pass before a pull request can be merged.

### 5. Open the pull request

Describe **what changed and why**. If it fixes an issue, say which one — `Fixes #42`.

A maintainer reviews it, and it gets merged. If changes are requested, they
land on your branch — keep the pull request open and push more commits to it.

## What gets reviewed

| Area | What we care about |
|---|---|
| **Correctness** | Does it work? Is there a test that proves it? |
| **Security** | Does it widen access? Does it weaken a control? Anything touching auth, crypto, ABAC or the ledger gets a careful read. |
| **Honesty** | Does the UI claim more than the system actually does? This is a hard rule — a template answer must never be presented as model output. |
| **Tests** | New behaviour needs a test. Bug fixes need a test that fails before the fix. |
| **Consistency** | Match the existing structure rather than introducing a new pattern. |

## Code of Conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security issues

**Do not** open a public issue for a vulnerability. Follow
[SECURITY.md](SECURITY.md) instead.

## Reporting something else

Open an issue with the bug report template. Include the version, your OS, the
exact steps, and what you expected to happen. If it is a security concern,
say so in the title — it will be routed privately.
