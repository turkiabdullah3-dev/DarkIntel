# Third-party dependency notices

DarkIntel uses the following direct dependencies. Versions are the audited installed/locked versions on 2026-08-13; accepted ranges remain defined by the requirement and package manifests. This inventory is informational and does not resolve the separate DarkFox provenance or licensing issue.

## Python runtime

| Package | Audited version | License | Source |
|---|---:|---|---|
| FastAPI | 0.141.1 | MIT | PyPI |
| Starlette | 1.6.0 | BSD-3-Clause | PyPI |
| Pydantic | 2.13.4 | MIT | PyPI |
| Uvicorn | 0.52.2 | BSD-3-Clause | PyPI |
| Requests | 2.34.2 | Apache-2.0 | PyPI |
| Beautiful Soup | 4.15.0 | MIT | PyPI |
| Filelock | 3.32.2 | MIT | PyPI |

## Python development and audit tools

| Package | Audited version | License | Source |
|---|---:|---|---|
| pytest | 8.4.2 | MIT | PyPI |
| pytest-cov | 6.3.0 | MIT | PyPI |
| Bandit | 1.9.4 | Apache-2.0 | PyPI |
| pip-audit | 2.10.1 | Apache-2.0 | PyPI metadata classifier |
| httpx2 | 2.10.0 | BSD-3-Clause | PyPI |

## Frontend runtime

| Package | Locked version | License | Source |
|---|---:|---|---|
| React | 19.2.8 | MIT | npm registry |
| React DOM | 19.2.8 | MIT | npm registry |
| React Router DOM | 7.18.2 | MIT | npm registry |
| Cytoscape.js | 3.34.1 | MIT | npm registry |
| Phosphor Icons React | 2.1.10 | MIT | npm registry |

TanStack Query is not a current dependency; DarkIntel uses local React state and custom hooks.

## Frontend development tools

| Package | Locked version | License | Source |
|---|---:|---|---|
| Vite | 7.3.6 | MIT | npm registry |
| TypeScript | 5.8.3 | Apache-2.0 | npm registry |
| Vitest | 3.2.7 | MIT | npm registry |
| Vite React plugin | 5.2.0 | MIT | npm registry |
| Testing Library React | 16.3.2 | MIT | npm registry |
| Testing Library jest-dom | 6.9.1 | MIT | npm registry |
| jsdom | 26.1.0 | MIT | npm registry |

Transitive dependencies remain recorded in the Python environment metadata and `dashboard/frontend/package-lock.json`. Before release, the maintainer should regenerate this inventory in the intended build environment and confirm whether any license requires additional attribution or notice text.
