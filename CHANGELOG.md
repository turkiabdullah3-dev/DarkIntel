# Changelog

## [Unreleased]

This unreleased work establishes **DarkIntel — CTI & OSINT Investigation Platform**, maintained by Turki Almuraykhi and developed from the legacy DarkFox project by Aryan Guenthner.

### Added

- Repository guidance for coding and review agents, plus reproducible Ruff, Pyright, and secret-scanning quality gates.
- Modular case, collection, IOC, enrichment, timeline, relationship-graph, and local dashboard layers.
- Atomic JSON persistence, bounded cross-process locks, case backups, integrity verification, and a synthetic offline demo.
- Production SPA serving, health reporting, security headers, CI, security audits, and container packaging.

### Changed

- Reimplemented the investigation workflow as a testable Python core, retained historical attribution, and excluded unresolved upstream source from the release candidate.
- Isolated Cytoscape behind route-level frontend code splitting.
- Constrained Python dependencies for reproducible compatibility.

### Security

- Neutralized spreadsheet formula/DDE triggers across all IOC CSV fields while preserving canonical JSON values.
- Rejected non-loopback dashboard binds by default and required an explicit warning-producing unsafe override.
- Loopback dashboard defaults, restricted development CORS, hostile-string rendering, bounded queries, atomic writes, path validation, and non-root container execution.
- Redistribution and relicensing remain blocked pending confirmation of the missing upstream license file.
