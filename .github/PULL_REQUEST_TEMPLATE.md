## What this changes

<!-- One or two sentences. What does this pull request do, and why? -->

Closes #<!-- issue number -->

## Why

<!-- The problem being solved. Link any related issue. -->

## How

<!-- The approach, in a few bullets. Note anything that could affect existing behaviour. -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (existing behaviour changes)
- [ ] Documentation or refactor (no behaviour change)

## Checklist

- [ ] `cd backend && venv/bin/python -m pytest tests/ -q` passes
- [ ] `cd frontend && npm run build` passes
- [ ] New behaviour has a test; bug fixes have a test that failed before the fix
- [ ] No secrets, API keys or real case data in the diff
- [ ] Does **not** widen access or weaken a security control
- [ ] The UI does not claim more than the system actually does

## Security

<!--
Does this touch authentication, crypto, ABAC, the ledger, the leak tracker or
the AI adapters? If so, describe what a reviewer should look at hardest.
-->
