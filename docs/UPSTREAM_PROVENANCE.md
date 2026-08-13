# Upstream provenance and separation record

Audit date: 2026-08-13

## Upstream record

- Project: DarkFox
- Author: Aryan Guenthner
- Repository: https://github.com/aryanguenthner/darkfox
- Observed license evidence: the historical README references GPL-3.0, but the reviewed snapshot contains no authoritative root `LICENSE` or `COPYING` file.

Files present in the cloned upstream snapshot before separation:

| Relative path | SHA-256 | Classification | Source |
|---|---|---|---|
| `darkfox.sh` | `135f3f1d8acd26f58f212a8b39eab44416efc1f1b02ce95ae0f4da915e7e58c0` | E — upstream DarkFox source | Upstream repository |
| `onion_verifier.py` | `142cedcf4c38f3cbcd1ffae5797666e7148ad88c45d534ecc909cd490313725b` | E — upstream DarkFox source | Upstream repository; the shell script also references the upstream raw URL |
| `DarkFox.desktop` | `7e9cf1f7856c5731e6615b83bc3a11585d9807d3582ae62ce88a33b4c1d819df` | E — upstream DarkFox source | Upstream repository |

No upstream file contents are reproduced here.

## Engineering separation findings

DarkIntel has no import, subprocess, file-read, Docker, CI, demo, test, or startup dependency on the three upstream files. Ahmia, PyAhmia, GoWitness, TorGhostNG, systemd control, sudo, and shell discovery orchestration are absent from the DarkIntel runtime.

Targeted manual comparison found no copied or substantially similar implementation requiring rewrite:

- `darkintel/verifier.py` uses strict Tor v3 URL parsing, typed results, injectable HTTP sessions, bounded timing, response hashing, and one GET request. It does not reproduce the upstream script's fixed CSV workflow, HEAD/GET split, thread pool, title fallback, or Tor restart behavior.
- `darkintel/tor.py` performs an unprivileged socket reachability check. It contains no systemd, process, signal, sudo, or TorGhostNG control logic.
- `darkintel/evidence.py` implements case-scoped atomic metadata/body persistence and IOC exports. The upstream script has no equivalent evidence model.
- `darkintel/cases.py` implements validated JSON case lifecycle and locked sequential IDs. The upstream files have no case model.
- `main.py` is an argparse application over typed DarkIntel modules. It does not call or reproduce the upstream interactive shell workflow.
- IOC extraction, governed enrichment, timeline, graph, dashboard, backup, integrity, release export, and synthetic demo components have no corresponding implementation in the reviewed upstream files.

These are engineering observations, not a legal conclusion. Behavioral concepts such as checking Tor reachability, requesting an onion URL, extracting an HTML title, and recording results are generic requirements; the current implementation is independently structured and tested.

## Complete file classification

### A — Independent DarkIntel implementation

- `darkintel/**/*.py`
- `dashboard/backend/**/*.py`
- `dashboard/frontend/src/**/*.{ts,tsx,css}` and `dashboard/frontend/index.html`
- `main.py`
- `tests/**/*.py`
- `.github/workflows/*.yml`
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.gitignore`, `.env.example`, `config.example.toml`
- `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/*.md`, `THIRD_PARTY_NOTICES.md`

### B — Generated/build/runtime artifacts

- `dashboard/frontend/dist/`, `dashboard/frontend/node_modules/`
- `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.tsbuildinfo`
- local `cases/`, `backups/`, `.env`, coverage output, lock files, logs, and temporary files

These are excluded from the public release tree.

### C — Maintainer-provided branding assets

- Active: `dashboard/frontend/src/assets/branding/logo.webp`, `logo-mark.webp`, `favicon.png`
- Authoritative source retained only in the working tree: `source-logo.jpg`

The assets were provided as the maintainer's personal/project branding. Written confirmation of ownership or redistribution permission remains a release-approval requirement. The source JPEG is excluded from the exported public tree because it is not needed at runtime.

### D — Third-party dependency/reference metadata

- `requirements.txt`, `requirements-dev.txt`
- `dashboard/frontend/package.json`, `dashboard/frontend/package-lock.json`

Dependencies are installed from their normal package indexes and are not vendored. Direct-license inventory appears in `THIRD_PARTY_NOTICES.md`.

### E — Upstream DarkFox source

- The three hashed files listed above. They were removed from the release-candidate worktree after dependency and regression checks.

### F — Derived/copied upstream implementation

- None identified by the targeted manual comparison.

### G — Uncertain provenance

- No source-code files identified.
- Branding redistribution remains approval-dependent as described under class C because repository contents alone cannot prove ownership.

## Git history caveat

Deleting upstream files from the current tree does not remove them from the cloned repository's Git history. The recommended public-release strategy is a fresh `DarkIntel` repository with one initial commit copied from the validated public release tree. History rewriting is possible but is not recommended here and was not performed.
