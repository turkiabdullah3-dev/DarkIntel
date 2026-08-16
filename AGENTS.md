# DarkIntel agent guide

DarkIntel is a local-first CTI/DFIR investigation platform. Preserve its workflow:

`Evidence / Target -> IOC Extraction -> Enrichment -> Timeline -> Relationship Graph -> Analyst Findings / Reporting`

## Architecture

- `darkintel/`: typed domain logic, case/evidence storage, extraction, enrichment, timeline, and graph.
- `dashboard/backend/`: FastAPI adapters and local API services; analytical rules belong in `darkintel/`.
- `dashboard/frontend/`: React/TypeScript presentation; do not duplicate backend analysis here.
- `main.py`: supported CLI and local dashboard entry point.
- `tests/`: mocked/offline unit, integration, regression, and security tests.

Read `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, and relevant `docs/` before changing code. Reuse existing abstractions and do not create a competing architecture.

## Non-negotiable semantics

- An IOC is not automatically malicious.
- Correlation is not attribution.
- A provider detection is a third-party claim, not ground truth.
- Confidence is not threat risk.
- Observations and system-generated facts remain separate from analyst conclusions.
- Never infer an APT, actor, ownership, compromise, or intent without explicit evidence.
- Preserve source, provider, timestamps, case ID, and provenance for analytical records.

## Evidence integrity

- Never silently modify or replace original evidence.
- Preserve SHA-256, UTC timestamps, source and case identifiers, and derived-artifact relationships.
- Validate case IDs and filesystem paths before access; reject traversal and unsafe archive paths.
- Treat extracted IOCs, enrichment, timelines, and graphs as derived artifacts, not source evidence.
- Keep canonical writes atomic and bounded; preserve existing locking and integrity contracts.

## Security boundaries

All inputs are hostile. Account for SSRF, path/command injection, XSS, unsafe redirects or deserialization, malicious filenames, malformed data, CSV formula injection, secrets exposure, and resource exhaustion. Network code requires explicit opt-in, HTTPS/TLS validation, fixed or validated destinations, bounded redirects and response sizes, timeouts, rate limits, normalized errors, and no secrets in logs. Never weaken Tor isolation, loopback defaults, evidence controls, or provider-consent boundaries. Do not add offensive automation, credential harvesting, payloads, or uncontrolled crawling.

## Development and validation

Use Python 3.11+ and Node.js 22. Work on a dedicated branch, never directly on `main`. Use focused conventional commits (`feat:`, `fix:`, `security:`, `refactor:`, `test:`, `docs:`, `ci:`, `perf:`, `chore:`).

Run from the repository root after installing `requirements.txt` and `requirements-dev.txt`:

```bash
python -m compileall -q darkintel dashboard main.py tests
python -m ruff check darkintel dashboard main.py tests
python -m pyright
python -m pytest -q
cd dashboard/frontend
npm ci
npm run typecheck
npm test
npm run build
```

Run the security commands in `CONTRIBUTING.md` when dependencies, inputs, networking, persistence, or CI change.

## Testing and completion

Every meaningful behavior change needs focused tests. Cover malformed and oversized input, duplicates, invalid identifiers and timestamps, provider failures/timeouts, unauthorized network attempts, hostile encodings, missing files, and graph/provenance integrity where relevant. Tests must not contact live Tor or providers.

A change is done only when implementation and tests are complete; compile, lint, type, test, and affected frontend checks pass; security and CTI/DFIR semantics are reviewed; documentation is current; no secrets or debug artifacts are present; and the diff is small and ready for independent architecture/security review. Report exact commands and failures—never claim checks that were not run.

## AI coding agents

Inspect before editing, state expected files, implement the smallest compatible solution, and review the final diff. Do not rewrite the project, add heavy dependencies without justification, invent attribution or risk scores, expose the unauthenticated dashboard, or begin unrelated product work. Preserve user changes in a dirty worktree and ask before destructive or externally visible actions.
