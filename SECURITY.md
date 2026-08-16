# Security policy

This policy covers DarkIntel. Historical DarkFox attribution and provenance are documented separately; upstream tooling is not part of the release tree.

## Supported versions

The unreleased `1.0.0` refactor on `refactor/core-v0.1` is the only version currently receiving security hardening. No release is declared supported until the maintainer completes the release and license review.

## Reporting a vulnerability

Use GitHub Security Advisories for private reporting when that feature is enabled for the repository. If no private channel is available, contact the repository maintainer without publishing exploit details. Do not include API keys, credentials, real investigation data, illegal content, evidence bodies, or identifying analyst information in a report; use synthetic reproduction data.

## Security assumptions

The dashboard is a local, single-user workstation service. It defaults to loopback and has no authentication or authorization. The supported CLI rejects every non-loopback IP and unrecognized hostname by default; `--allow-non-loopback` is an explicit unsafe override that warns about exposure but adds no authentication, authorization, or TLS. Direct Uvicorn invocation does not enforce this CLI policy. Do not expose DarkIntel to an untrusted network. Provider access is opt-in from the CLI; normal dashboard reads do not contact third parties. Case storage and backups may contain sensitive material and require host-level access controls.

IOC and timeline CSV exports neutralize fields whose first non-whitespace character can trigger a spreadsheet formula. This changes only the analyst-facing CSV representation; canonical JSON evidence and analytical values remain unchanged.

Historical upstream scripts and the desktop launcher are excluded from the DarkIntel release candidate and Docker context. Their hashes and separation rationale are recorded in `docs/UPSTREAM_PROVENANCE.md`.

## License and release status

The upstream README historically references GPL-3.0, but this snapshot has no authoritative root `LICENSE` or `COPYING` file. Public redistribution and release remain blocked until the maintainer resolves the upstream licensing basis.
