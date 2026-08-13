# DarkIntel public release tree

The public release must be created from the allowlisted exporter, not by publishing the current cloned repository or copying its Git history.

```bash
python main.py release-tree export --output /path/to/empty/DarkIntel
```

## Allowlisted tree

```text
DarkIntel/
├── .github/
├── darkintel/
├── dashboard/
├── docs/
├── packaging/
├── scripts/
├── tests/
├── .dockerignore
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── Dockerfile
├── README.md
├── SECURITY.md
├── THIRD_PARTY_NOTICES.md
├── config.example.toml
├── docker-compose.yml
├── main.py
├── requirements.txt
└── requirements-dev.txt
```

The frontend source tree includes the active optimized branding assets. `source-logo.jpg` is intentionally excluded because it is not required to build or run the application.

## Must not ship

- The upstream source files recorded in `UPSTREAM_PROVENANCE.md`
- `.git/` or history from the cloned upstream repository
- `cases/`, `backups/`, `.env`, secrets, logs, coverage output, lock files, or temporary files
- `node_modules/`, frontend `dist/`, Python caches, pytest caches, or TypeScript build metadata
- developer-specific filesystem paths or symlinks

The exporter fails closed for missing allowlisted files, non-empty destinations, excluded names, symlinks, probable embedded secrets, developer-specific paths, upstream source basenames, and unexpected implementation-level references to upstream filenames.

## Fresh repository plan

1. Resolve the upstream license-history review and branding redistribution approval.
2. Export into a new empty directory outside this repository.
3. Run the complete test, audit, frontend, demo, and Docker verification from the exported tree.
4. Review attribution and third-party notices.
5. Initialize a new Git repository named `DarkIntel` in the exported directory.
6. Create a fresh initial commit only after explicit maintainer approval.

Do not copy `.git`, upstream source, runtime cases, build output, or local environment files. Preserve the concise historical attribution in the README and provenance document without claiming upstream endorsement or license rights.
