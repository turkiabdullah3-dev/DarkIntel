# Contributing

Use Python 3.11 or newer and Node.js 22. Install Python dependencies with `python -m pip install -r requirements.txt -r requirements-dev.txt`; install frontend dependencies with `npm ci` in `dashboard/frontend`.

Before opening a pull request, run:

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

Run the lightweight security baseline from the repository root:

```bash
detect-secrets scan --all-files --exclude-files '(\.git|\.venv|\.ruff_cache|\.pytest_cache|__pycache__|node_modules|dist|coverage|\.tsbuildinfo)' --baseline .secrets.baseline
git diff --exit-code -- .secrets.baseline
python -m bandit -r darkintel dashboard/backend main.py
python -m pip_audit -r requirements.txt
cd dashboard/frontend
npm audit --omit=dev
```

Secret detection rescans source content against `.secrets.baseline`; the diff check fails when a scan adds findings. If a deliberate synthetic value is detected, add a reviewed inline allowlist pragma. Never baseline or allowlist a real credential.

Keep analytical logic in `darkintel`, HTTP adaptation in `dashboard/backend`, and presentation in `dashboard/frontend`. Preserve bounded inputs, atomic canonical writes, case isolation, provenance, loopback defaults, and explicit network consent. Pull requests should describe behavioral and security impact, include focused tests, and update documentation where needed.

Never commit secrets, `.env` files, real case data, real illegal content, live threat infrastructure, or sensitive provider payloads. Fixtures and demos must be synthetic and use reserved domains and documentation IP ranges.
