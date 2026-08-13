# Contributing

Use Python 3.11 or newer and Node.js 22. Install Python dependencies with `python -m pip install -r requirements.txt -r requirements-dev.txt`; install frontend dependencies with `npm ci` in `dashboard/frontend`.

Before opening a pull request, run:

```text
python -m compileall -q darkintel dashboard main.py
python -m pytest
python -m bandit -r darkintel dashboard/backend main.py
python -m pip_audit -r requirements.txt
cd dashboard/frontend
npm run typecheck
npm test
npm run build
npm audit --omit=dev
```

Keep analytical logic in `darkintel`, HTTP adaptation in `dashboard/backend`, and presentation in `dashboard/frontend`. Preserve bounded inputs, atomic canonical writes, case isolation, provenance, loopback defaults, and explicit network consent. Pull requests should describe behavioral and security impact, include focused tests, and update documentation where needed.

Never commit secrets, `.env` files, real case data, real illegal content, live threat infrastructure, or sensitive provider payloads. Fixtures and demos must be synthetic and use reserved domains and documentation IP ranges.
