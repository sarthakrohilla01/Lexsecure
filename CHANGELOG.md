# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] — 2026-11-12

### Added
- **In-app Guide** — a documentation section in the left sidebar with six tabs
  (start here, accounts, app tour, every control, glossary, troubleshooting).
  Reachable at `/guide` without a session.
- **Server-side token revocation** — `POST /api/auth/logout` blacklists the
  presented JWT in a new `revoked_tokens` table, checked on every request.
- **Real LLM answer synthesis** via NaraRouter, Gemini, Ollama or any
  OpenAI-compatible endpoint, with automatic failover between models and an
  honest offline fallback.
- **Audit export attestation** — CSV and JSON exports carry an `X-Export-SHA256`
  header and the export is itself recorded in the trail.
- **Zero-width leak tracker** — downloaded text evidence is invisibly stamped
  with the downloader's identity, recoverable through the Leak Investigator.
- **Two-Man Rule** — sealed documents require a supervisor grant before they
  open, with expiring unlock tokens.
- **Continuous integrity monitor** — re-verifies every stored version against
  three independent anchors on a schedule and raises live tamper alerts.
- **In-app document preview** — PDFs, images and text render decrypted in the
  browser.
- **Court package generator** — Section 65B / BSA evidentiary manifest with
  hashes, signatures and ledger blocks.

### Changed
- Frontend now serves the API from a same-origin `/api` path, proxied by Vite in
  development and by nginx in production.
- Ledger block numbers are allocated under a lock so concurrent writes cannot
  fork the hash chain.
- Workflow approvals and rejections are now ABAC-checked.
- Timestamps use a shared timezone-aware UTC helper instead of the deprecated
  `datetime.utcnow()`.
- Pydantic v2 `ConfigDict` replaces the deprecated class-based `Config`.

### Fixed
- The live feed stopped refreshing once it reached fifty events.
- The WebSocket could be opened twice, and a stale close could orphan the live
  connection.
- The tamper alert could stay on screen indefinitely.
- A network blip during session restore logged the user out.
- A non-string FastAPI `detail` could crash the React tree.
- `UserResponse` omitted `is_active`, so the admin panel showed every officer
  as deactivated.
- The audit export filename, count and digest were unreachable from the browser.

## [1.0.0]

Initial public release: case management, encrypted document storage with
versioning, malware scanning, the custody ledger, semantic search, the audit
trail and RBAC/ABAC access control.

[Unreleased]: https://github.com/sarthakrohilla01/Lexsecure/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/sarthakrohilla01/Lexsecure/releases/tag/v2.0.0
[1.0.0]: https://github.com/sarthakrohilla01/Lexsecure/releases/tag/v1.0.0
