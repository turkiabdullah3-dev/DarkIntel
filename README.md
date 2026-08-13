<p align="center">
  <img src="docs/assets/darkintel-logo-transparent.png" alt="DarkIntel logo" width="600">
</p>

<h1 align="center">DarkIntel</h1>

<p align="center"><strong>CTI &amp; OSINT Investigation Platform</strong></p>

<p align="center">Maintained by Turki Almuraykhi</p>

DarkIntel is an independently maintained, local-first investigation platform for authorized dark-web research, evidence handling, IOC analysis, governed enrichment, timelines, and relationship graphs. It was historically inspired by the [DarkFox project by Aryan Guenthner](https://github.com/aryanguenthner/darkfox); upstream source files are not included in the DarkIntel release tree.

> Use DarkIntel only for lawful, authorized CTI, OSINT, DFIR, academic, or security research. It does not provide exploitation, credential collection, persistence, payload delivery, or offensive automation.

## Architecture

The modern core targets Python 3.11+ and is intentionally independent of system administration:

```text
darkintel/
├── models.py       # OnionResult and InvestigationCase
├── tor.py          # unprivileged SOCKS-port detection
├── verifier.py     # validation and passive HTTP observation through Tor
├── cases.py        # JSON case lifecycle
├── evidence.py     # result metadata and optional supplied-body persistence
└── utils.py        # safe case IDs and JSON helpers
main.py             # argparse CLI
tests/              # mocked unit tests (no live Tor required)
```

The supported application is implemented through the DarkIntel Python core and dashboard. Historical provenance is recorded in `docs/UPSTREAM_PROVENANCE.md`.

## Installation

Create and activate a virtual environment, then install the runtime dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For development and tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Runtime dependencies are defined in `requirements.txt`; test and audit tooling remains in `requirements-dev.txt`.

## Tor requirements

Run a Tor client with a SOCKS listener before verification. The default endpoint is `127.0.0.1:9050`; it can be changed with `--tor-host` and `--tor-port`.

```bash
python main.py tor-check
python main.py tor-check --tor-host 127.0.0.1 --tor-port 9050 --timeout 2
```

The Python core only checks whether the configured TCP endpoint is reachable. It never starts or restarts Tor, changes firewall or DNS rules, modifies browser settings, changes timezone, or invokes `sudo`. A reachable port establishes listener availability, not proof of Tor routing or anonymity.

## CLI usage

Verify one Tor v3 onion URL and emit JSON:

```bash
python main.py verify --url http://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.onion
```

Only `http` and `https` are supported. Inputs must have a 56-character base32 Tor v3 hostname. Clearnet domains, embedded credentials, invalid ports, malformed hosts, and unsupported schemes are rejected. A missing scheme is normalized to `http`; fragments are not sent.

Useful options can appear on the relevant command:

```bash
python main.py verify --url URL --tor-host 127.0.0.1 --tor-port 9050 --timeout 15
python main.py --cases-dir ./cases case list
python main.py --verbose tor-check
```

## Case workflow

Create and inspect cases:

```bash
python main.py case create --name "Ransomware Investigation" --description "Authorized CTI collection" --tag ransomware
python main.py case list
python main.py case show CASE-2026-0001
python main.py case update CASE-2026-0001 --status archived
python main.py case close CASE-2026-0001
```

Case IDs use UTC year and a sequential number such as `CASE-2026-0001`. IDs are validated before filesystem use to prevent traversal. Case metadata is JSON; no database is used.

Investigate a newline-delimited input file:

```bash
python main.py investigate --case CASE-2026-0001 --input onions.txt
```

Blank lines and lines beginning with `#` are ignored. Every target produces a structured result, including validation and network failures, so one bad target does not stop the batch. The command prints a concise per-target status and final count.

## Evidence format

Creating a case produces:

```text
cases/CASE-2026-0001/
├── case.json
├── results/
├── evidence/
├── screenshots/
├── extracted_iocs/
├── logs/
└── reports/
```

Investigation results are timestamped JSON files under `results/`. Each observation can include:

```json
{
  "url": "http://…onion/",
  "is_live": true,
  "status_code": 200,
  "title": "Example",
  "response_time_ms": 823.4,
  "content_type": "text/html; charset=utf-8",
  "final_url": "http://…onion/",
  "sha256": "…",
  "error": null,
  "observed_at": "2026-08-13T00:00:00Z"
}
```

The verifier hashes the downloaded response body in memory. The CLI currently persists observation metadata, not page bodies. The evidence API can persist a body explicitly supplied by a caller and verifies its SHA-256 first. DarkIntel does not crawl links or automatically download linked files.

## Security model

The modern workflow provides:

- strict Tor v3 URL validation before any request;
- remote DNS resolution through `socks5h`;
- explicit connect/read request timeout;
- a reusable `requests.Session` with scoped proxy settings;
- normal TLS certificate verification for HTTPS;
- passive GET requests only, with redirect outcomes recorded;
- UTC timestamps, response hashing, structured failures, and no page-content logging;
- validated case IDs and atomic JSON metadata replacement.

HTTP error responses such as 404 are marked reachable because an HTTP service answered; `error` records the status. Network failures and validation failures are marked not live.

These controls do not make hostile content safe, prevent browser fingerprinting, defeat traffic analysis, authenticate an onion operator, or create a forensic chain of custody by themselves. Use an isolated, appropriately governed research environment.

## Upstream separation

The historical upstream tooling is not part of the supported application or public release tree. The engineering audit, recorded file hashes, behavioral comparison, and exclusions are maintained in `docs/UPSTREAM_PROVENANCE.md` and `docs/PUBLIC_RELEASE_TREE.md`.

The DarkIntel core uses independently structured, unprivileged Python services and does not invoke upstream scripts.

Use `main.py` for all supported integrations.

## Limitations

- Only Tor v3 onion URLs are accepted; v2 addresses are obsolete and unsupported.
- Tor detection checks the configured listener, not the Tor protocol or exit identity.
- Verification is sequential and intentionally performs no crawling or linked-file collection.
- Case numbering is suitable for a single local process; concurrent creators need locking in a later release.
- JSON storage has no database indexing, access controls, signatures, retention policy, or evidence manifest.
- Enrichment, reporting, timelines, relationship graphs, screenshots, and a dashboard are not implemented in the Python core yet.
- Response size is not currently capped, so targets should be selected and operated under appropriate research controls.

## Testing

The supported release baseline is Python 3.11+ and Node.js 22. Production Python packages use narrow compatible release ranges. FastAPI 0.141.x and Starlette 1.6.x are paired with the current `httpx2` test transport; this removes the deprecated legacy TestClient shim without pinning to vulnerability-affected Starlette releases. CI installs frontend packages reproducibly with `npm ci`.

The unit suite mocks sockets and HTTP calls and therefore does not require Tor:

```bash
python -m compileall -q darkintel main.py tests
python -m pytest -q
```

Tests cover models and UTC serialization, valid normalization, invalid and clearnet rejection, credentials and scheme validation, Tor availability failures, successful and HTTP-error observations, timeout handling, malformed HTML tolerance, SHA-256 generation, case creation/loading/update/close, directory layout, evidence persistence, and case path validation.

## IOC extraction

DarkIntel can extract normalized intelligence indicators from local evidence that has already been collected. Extraction is passive string parsing: it does not visit URLs, resolve hosts, contact identity or cryptocurrency services, execute commands or JavaScript, render HTML, or download referenced content.

```bash
python main.py extract --case CASE-2026-0001 --file evidence.html
python main.py extract --case CASE-2026-0001 --file notes.txt
python main.py extract --case CASE-2026-0001 --file notes.txt --format json
```

The default output is a count-only analyst summary and does not print indicator values. `--format json` prints the per-file extraction result when structured output is explicitly requested. Both modes merge the result into the case exports.

### Supported indicator types

The controlled IOC types are:

| Family | Types | Normalization and validation |
|---|---|---|
| Network | `ipv4`, `ipv6`, `domain`, `url`, `onion` | IPs use `ipaddress`; IPv6 is compressed; domain, URL scheme, and host casing are normalized; URLs are parsed without execution; onions reuse strict 56-character Tor v3 validation. |
| Hashes | `md5`, `sha1`, `sha256`, `sha512` | Exact-length hexadecimal tokens are normalized to lowercase. |
| Cryptocurrency | `bitcoin`, `monero` | Bitcoin Base58Check and Bech32/Bech32m checksums are validated; Bech32 is lowercase-normalized. Standard 95-character Monero address shape and alphabet are validated without blockchain access. |
| Identities | `email`, `telegram` | Email domain casing is normalized; `@name`, `t.me/name`, and `telegram.me/name` become `@name`. Nothing contacts Telegram. |
| Vulnerabilities | `cve` | Well-formed CVE identifiers are normalized to uppercase. Extraction does not imply exploitation or maliciousness. |

Network classifications such as `public`, `private`, `loopback`, `reserved`, and `multicast` are recorded as tags where applicable. Filenames with common extensions are excluded from domain candidates to reduce obvious false positives.

### Confidence semantics

Confidence measures extraction validity, not maliciousness or threat risk:

- `1.0`: strict parser, checksum, exact-length, or strict identifier validation;
- `0.9`: strongly formatted and parsed URL or identity;
- `0.8`: validated domain syntax or constrained Monero address shape.

No enrichment or threat scoring occurs in this phase.

### Context, limits, and storage

Each IOC stores normalized whitespace from at most 80 characters before and after its occurrence. The engine defaults are 5,000,000 input characters, 10,000 unique IOCs per extraction, and a configurable context window capped at 500 characters per side. Limit events are returned as warnings instead of terminating the entire extraction. The CLI additionally stops reading a local file after 20,000,000 bytes and reports truncation.

Per-file indicators are deduplicated by `(type, normalized_value)`. Case-level merging uses the same key, increments `observation_count`, preserves unique `sources`, keeps the earliest `first_seen`, and retains the highest extraction confidence. The canonical and analyst exports are:

```text
cases/CASE-YYYY-NNNN/extracted_iocs/indicators.json
cases/CASE-YYYY-NNNN/extracted_iocs/indicators.csv
```

JSON is canonical. CSV contains type, original and normalized values, confidence, source, first-seen time, bounded context, tags, observation count, and sources.

For HTML evidence, DarkIntel removes script, style, noscript, and template elements, extracts visible text and anchor `href` strings, and performs no rendering or resource loading. Malformed HTML is handled by BeautifulSoup's local parser.

### Known extraction limitations

- Extraction identifies syntactically valid indicators; it does not establish ownership, reachability, compromise, reputation, or malicious intent.
- Monero detection validates standard-address length, prefix, and Base58 alphabet but not the CryptoNote Keccak checksum because no heavy cryptocurrency dependency is introduced.
- Domain and identity recognition is heuristic and can produce false positives or miss unusual valid forms.
- URL normalization intentionally avoids semantic transformations of paths and query strings.
- Case export replacement is atomic, but simultaneous writers are not yet locked.

Extraction and enrichment are separate stages. **Extraction** identifies and normalizes indicators already present in evidence. **Enrichment** adds governed offline or explicitly selected third-party context while preserving provenance.

## Governed evidence enrichment

Enrichment adds attributable provider observations to extracted case IOCs. It is opt-in, sequential, rate-limited, cached, and separate from extraction confidence or analyst risk assessment. The default policy enables only the zero-network `local` provider and sets `allow_network = false`.

```bash
# Offline metadata only
python main.py enrich --case CASE-2026-0001 --provider local

# Explicitly share normalized IOCs with selected network providers
python main.py enrich --case CASE-2026-0001 --provider rdap --allow-network
python main.py enrich --case CASE-2026-0001 --provider local --provider virustotal --allow-network --limit 20
```

The CLI prints counts rather than full provider responses. `--limit` is capped by the conservative policy maximum of 50 indicators per run.

### Provider matrix

| Provider | Network | Supported types | Authentication |
|---|---:|---|---|
| Local | No | IPv4, IPv6, domain, onion, MD5, SHA-1, SHA-256, SHA-512, CVE | None |
| RDAP | Yes | IPv4, IPv6, domain | None |
| VirusTotal | Yes | IPv4, domain, URL, MD5, SHA-1, SHA-256 | `DARKINTEL_VT_API_KEY` |
| AbuseIPDB | Yes | IPv4 | `DARKINTEL_ABUSEIPDB_API_KEY` |

`config.example.toml` documents recommended settings but is not automatically loaded by the current CLI. API keys are read only from environment variables. `.env` files are ignored; DarkIntel does not load them, print keys, write keys to cases, place keys in URLs, or retain authorization headers.

### Privacy and network boundary

Selecting a network provider with `--allow-network` shares the normalized IOC with that third party. It does not send case descriptions, analyst notes, evidence context, source filenames, or complete evidence documents. Onion, email, Telegram, cryptocurrency, and other unsupported types are never sent to a provider that does not explicitly declare support.

Provider requests use HTTPS, normal TLS certificate validation, explicit timeouts, fixed initial provider hosts, no system proxy changes, and no shell commands. VirusTotal and AbuseIPDB redirects are refused. RDAP may follow at most two HTTPS redirects from the RDAP bootstrap service to a public registry host; HTTP, localhost, local-domain, credential-bearing, and non-public literal-IP redirect targets are rejected. Enrichment is not routed through Tor automatically.

### Policy, rate limits, and errors

Defaults are 50 indicators per run, 25 actual HTTP attempts per provider, a minimum 250 ms interval between provider requests, and at most one retry for HTTP 429. `Retry-After` waits are capped at five seconds, and the request ceiling includes retries. Processing is deterministic and sequential; there is no uncontrolled concurrency or aggressive retry behavior.

Provider errors are normalized as `configuration_error`, `unsupported_indicator`, `network_error`, `timeout`, `authentication_error`, `rate_limited`, `not_found`, `provider_error`, or `parse_error`. A failed provider does not terminate the case run and sensitive exception internals are not included in analyst records.

### Cache, provenance, and storage

The case-scoped cache key includes provider, IOC type, and normalized IOC value. Successful records default to a 24-hour TTL; failures are cached for at most one hour. Valid cache entries prevent a provider request and are returned with `cached: true`. Cache files are capped at 5,000 entries per case.

```text
cases/CASE-YYYY-NNNN/enrichment/
├── records.json
├── summary.json
└── cache/
```

`records.json` appends run results rather than modifying `extracted_iocs/indicators.json`. Every record identifies the provider, indicator type and value, query time, success, cache status, normalized bounded summary, expiry, and normalized error. Provider claims remain separate; they are not merged into an opaque consensus. Raw responses are not retained, avoiding unlimited provider payload storage and secret-bearing request metadata. Responses larger than 1,000,000 bytes are rejected.

`summary.json` contains bounded factual observations such as provider-reported detection counts, abuse scores, private/reserved classification, or unavailable results. These are provider claims, not automatic labels such as malicious, ransomware, APT, C2, compromised, or a unified threat score.

### Enrichment limitations

- Provider schemas and availability can change; summaries deliberately retain only a small supported field set.
- Provider confidence is not extraction confidence and is not a threat-risk score.
- VirusTotal detections and AbuseIPDB reports are third-party claims, not ground truth.
- RDAP registration interpretation varies by registry and no WHOIS fallback is executed.
- Cache and record files do not yet use cross-process locking.
- The example TOML configuration is documentation-only in this version.

## Investigation timeline

The investigation timeline is a derived, provenance-aware analytical index over existing case artifacts. Evidence files, verification results, extracted IOC records, and enrichment history remain the authoritative source data; building or rebuilding a timeline does not modify them.

```text
darkintel/timeline/
├── models.py       # controlled event types, UTC timestamps, stable IDs, bounds
├── builder.py      # offline artifact-to-event mapping
├── correlation.py  # exact deterministic correlations
├── store.py        # case persistence, notes, filters, summaries
└── exporters.py    # JSON, safe CSV, and Markdown
```

Timeline files are stored under:

```text
cases/CASE-YYYY-NNNN/timeline/
├── events.json
├── events.csv
├── events.md       # created when Markdown is requested
└── summary.json
```

JSON is canonical. CSV intentionally excludes large metadata. The summary contains total events, inclusive first/last timestamps, controlled event-type counts, unique object count, and bounded warnings; it does not contain a risk score.

### Supported event types

The controlled types are `case_created`, `case_updated`, `case_closed`, `target_discovered`, `target_verified`, `target_unreachable`, `evidence_collected`, `evidence_hashed`, `ioc_extracted`, `ioc_observed`, `enrichment_requested`, `enrichment_completed`, `enrichment_failed`, `enrichment_cache_hit`, and `analyst_note`.

Machine-generated events use stable UUIDv5 identifiers derived from case ID, event type, normalized timestamp, object type/value, and source. Rebuilds therefore replace the same logical generated event instead of duplicating it. Manual analyst notes use UUIDv4 identifiers and remain preserved across rebuilds.

### Timestamp and provenance semantics

All timestamps must be timezone-aware and are normalized to UTC:

- case lifecycle events use `created_at` or `updated_at`;
- target, evidence, and hash events use verification `observed_at`;
- IOC extraction and observation use `first_seen`;
- enrichment request, completion, failure, and cache events use provider `queried_at`;
- analyst notes use the supplied timestamp or the note-creation time.

An explicitly supplied non-UTC offset is retained as `original_timestamp` metadata. Missing timestamps are skipped with warnings rather than silently replaced with build time.

Machine events preserve bounded provenance including artifact-relative source, source record ID, evidence ID or hash, normalized indicator type/value, provider, provider summary, and cache/success state as applicable. Provider statements remain phrased as provider claims and are not converted into analyst conclusions.

### Correlation rules

Correlation is deliberately non-speculative. `related_ids` are added only when:

- normalized object type and value match;
- source identifiers match;
- an evidence SHA-256 exactly equals an extracted SHA-256 IOC.

These stable IDs and explicit correlations can support a later relationship graph, but no graph model, database, or visualization is implemented in this phase.

### Timeline CLI

```bash
python main.py timeline build --case CASE-2026-0001
python main.py timeline show --case CASE-2026-0001
python main.py timeline show --case CASE-2026-0001 --type enrichment_completed
python main.py timeline show --case CASE-2026-0001 --object example.com --object-type domain
python main.py timeline show --case CASE-2026-0001 --source evidence/body.bin
python main.py timeline show --case CASE-2026-0001 \
  --from 2026-08-13T07:00:00Z --to 2026-08-13T08:00:00Z
```

Time filters are inclusive. Invalid or timezone-naive timestamps are rejected.

Create an explicitly manual note:

```bash
python main.py timeline note --case CASE-2026-0001 \
  --title "Victim name confirmed" \
  --description "Confirmed from public company disclosure" \
  --timestamp 2026-08-13T10:30:00+03:00
```

Export deterministic representations:

```bash
python main.py timeline export --case CASE-2026-0001 --format json
python main.py timeline export --case CASE-2026-0001 --format csv
python main.py timeline export --case CASE-2026-0001 --format markdown
```

Default display is concise and does not dump metadata.

### Timeline resource and security controls

- Maximum stored timeline events: 100,000 per case; builders can set a lower bound.
- Machine descriptions: 4,000 characters; analyst-note descriptions: 10,000 characters.
- Titles: 500 characters; related IDs: 1,000; tags: 100.
- Metadata: bounded depth and collection sizes, 2,000-character values, and approximately 16 KiB per event. Oversized metadata is reduced with a SHA-256 reference to its bounded representation.
- Case IDs reuse strict `CASE-YYYY-NNNN` validation; artifact-provided source strings are labels and are never resolved as filesystem paths.
- JSON parsing uses standard safe deserialization and malformed source records are isolated with bounded warnings.
- CSV fields whose first non-whitespace character is `=`, `+`, `-`, or `@` receive a leading apostrophe to prevent spreadsheet formula execution.
- Markdown escapes HTML angle brackets and code delimiters to reduce future rendering injection risk.
- Timeline building performs no provider calls, URL visits, DNS lookups, shell execution, or other network access.

Timeline writes use atomic JSON replacement, but concurrent writers are not yet locked. The builder indexes current case JSON artifacts rather than maintaining a separately signed audit log, and repeated identical provider records with the same fingerprint collapse into one logical event. Filesystem-level acquisition times are not inferred when source timestamps are absent.

## Relationship graph

The relationship graph is deterministic, provenance-aware derived analytical data. Original evidence, verification, IOC, enrichment, and timeline artifacts remain the source of truth. Graph construction reads those artifacts locally and never modifies them or performs network access.

```text
darkintel/graph/
├── models.py       # controlled bounded nodes and edges
├── builder.py      # artifact-to-graph construction
├── correlation.py  # integrity checks and provenance merging
├── store.py        # JSON persistence and analyst objects
├── query.py        # bounded local queries and paths
└── exporters.py    # canonical JSON, GraphML, Cytoscape JSON
```

Case artifacts are stored under:

```text
cases/CASE-YYYY-NNNN/graph/
├── nodes.json
├── edges.json
├── graph.json
├── summary.json
├── graph.graphml      # when exported
└── cytoscape.json     # when exported
```

`graph.json` is canonical. The summary reports node and relationship counts, isolated nodes, connected components, and bounded warnings. It performs no threat scoring or advanced graph analytics.

### Controlled node and relationship types

Node types are `case`, `target`, `onion`, `evidence`, `ipv4`, `ipv6`, `domain`, `url`, `email`, `md5`, `sha1`, `sha256`, `sha512`, `bitcoin`, `monero`, `cve`, `telegram`, `provider`, `enrichment_record`, `timeline_event`, `analyst_entity`, `threat_actor`, and `organization`.

Relationship types are `contains`, `observed_in`, `extracted_from`, `derived_from`, `verified_as`, `hashed_as`, `enriched_by`, `reported_by`, `related_to`, `references`, `belongs_to_case`, `correlated_with`, `mentions`, and `associated_with`. Raw evidence cannot create arbitrary types.

Generated nodes use a UUIDv5 identity derived from case ID, node type, and normalized value. Generated edges use case ID, source node ID, controlled relationship, and target node ID. Rebuilds are idempotent. Supporting provenance is merged into the same logical edge rather than creating duplicates.

### Canonical directions and correlation rules

Only structured identifiers and exact normalized matches create edges:

- every non-case node `belongs_to_case` → its case;
- target `verified_as` → normalized onion hostname;
- evidence `derived_from` → target;
- evidence `hashed_as` → SHA-256 when the stored digest matches;
- evidence `contains` → IOC only when an IOC source exactly matches the evidence identifier;
- IOC `enriched_by` → provider only when provider and IOC normalized values match;
- enrichment record `references` → IOC and `reported_by` → provider;
- timeline event `references` → IOC, evidence, or target only when structured object type/value match.

No substring, title-text, co-occurrence, similarity, inferred actor, or low-confidence speculative relationships are generated. Reverse edges are not duplicated.

Relationship confidence describes support for the edge—not threat risk:

- `1.0`: direct identifier, digest, or structured record match;
- `0.95`: explicit evidence source reference;
- `0.9`: exact normalized IOC/provider enrichment relationship;
- `0.8` remains the intended minimum for future system-generated rules.

Every system edge contains bounded source-artifact provenance. Multiple source records merge provenance and keep the highest relationship confidence. Rebuilds retain previously recorded provenance for logical edges that still exist.

### Manual analyst entities and relationships

Analysts can explicitly add supported entity types:

```bash
python main.py graph node add --case CASE-2026-0001 \
  --type threat_actor --value "Example Group" --label "Example Group"
```

Manual relationships require two existing same-case nodes and a controlled relationship:

```bash
python main.py graph edge add --case CASE-2026-0001 \
  --source NODE_ID --target NODE_ID --relationship associated_with
```

Manual nodes and edges use UUIDv4, are marked `origin = analyst`, and survive rebuilds. Manual edge confidence defaults to `0.75`, clearly below the system relationship threshold, unless the analyst supplies another value. A rebuild never overwrites analyst-origin objects.

### Graph CLI and queries

```bash
python main.py graph build --case CASE-2026-0001
python main.py graph show --case CASE-2026-0001
python main.py graph nodes --case CASE-2026-0001 --type domain
python main.py graph neighbors --case CASE-2026-0001 --node NODE_ID
python main.py graph path --case CASE-2026-0001 --from NODE_A --to NODE_B --max-depth 4
python main.py graph export --case CASE-2026-0001 --format json
python main.py graph export --case CASE-2026-0001 --format graphml
python main.py graph export --case CASE-2026-0001 --format cytoscape
```

Queries support neighbors, nodes by type, edges by relationship through the Python API, exact type/value lookup, and shortest local paths. Path search uses bounded breadth-first traversal: depth defaults to four, cannot exceed six, and stops after 50,000 visited nodes.

GraphML is generated with the standard XML library, safely escapes hostile labels and values, preserves IDs and directed relationship types, and is never parsed as executable XML. Cytoscape-compatible JSON contains stable node and edge data consumed by the local dashboard.

### Graph resource, integrity, and security controls

- Maximum nodes: 100,000; maximum edges: 250,000.
- Node labels: 500 characters; values: 4,000 characters.
- Tags: 100; source IDs and edge provenance: 1,000 each.
- Attributes reuse bounded-depth, bounded-collection, approximately 16 KiB metadata handling.
- Graph validation rejects duplicate IDs, dangling edges, self-loops, unknown types, unknown relationships, and cross-case nodes or edges.
- Strict case ID validation prevents traversal; artifact source IDs are treated as labels rather than filesystem paths.
- JSON and Cytoscape exports use safe serialization assumptions; GraphML uses XML escaping.
- Graph traversal, connected-components calculation, and export operate locally without subprocesses, shell commands, URL visits, DNS, Tor, or provider calls.

Current graph limitations include no cross-process write locking, deletion/edit commands for analyst objects, temporal graph queries, advanced centrality/community analysis, signed provenance ledger, or graph database. Manual objects are trusted analyst assertions and remain clearly separated from system-generated facts.

## One-click Linux Launcher

On Kali Linux and other XDG-compatible desktops, install the user-local application launcher from the repository root:

```bash
./scripts/install-linux-launcher.sh
```

DarkIntel then appears in the applications menu. Clicking it checks the local `.venv`, builds the frontend only when its production output is missing or stale, starts the loopback-only dashboard, waits for the DarkIntel health endpoint, and opens `http://127.0.0.1:8000` in the default browser. A second click reuses the healthy instance instead of starting another server. Launcher logs and its managed PID are stored under `${XDG_STATE_HOME:-$HOME/.local/state}/darkintel/`.

The launcher never installs dependencies as root. Create `.venv` and install the project requirements first; Node.js/npm is needed only when a frontend rebuild is required. To remove only the applications-menu integration and installed icon:

```bash
./scripts/uninstall-linux-launcher.sh
```

Uninstalling the launcher does not remove the repository, cases, evidence, or other investigation data.

## CTI investigation dashboard

Phase 6 adds a separate local application layer under `dashboard/`. FastAPI exposes the existing case stores and analytical modules as a versioned, mostly read-only API; the React/TypeScript SPA presents those records without duplicating extraction, enrichment, timeline, or graph-correlation logic.

### Product branding

Dashboard identity is centralized in `dashboard/frontend/src/config/branding.ts`; API-facing identity lives in `dashboard/backend/branding.py`. The authoritative supplied artwork is retained as `dashboard/frontend/src/assets/branding/source-logo.jpg`. Faithful local WebP crops provide the active full symbol, compact mark, and favicon without fake vectorization, added text, or decorative effects. Identity fields and asset imports remain centralized for maintainable future changes.

The compact mark appears in the stable sidebar and top header, the complete symbol appears in the no-cases state, and browser metadata uses the favicon variant. Branding assets are local, CSP-compatible, and contain no remote references. Upstream DarkFox attribution and unresolved licensing documentation remain separate from this product identity.

### Development setup

Install the Python dependencies and start the backend on loopback:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m uvicorn dashboard.backend.app:app --host 127.0.0.1 --port 8000 --reload
```

OpenAPI documentation is then available locally at `http://127.0.0.1:8000/docs`. In another terminal, start the frontend:

```bash
cd dashboard/frontend
npm install
npm run dev
```

Vite serves `http://127.0.0.1:5173` and proxies `/api` to the backend. For a single-process production-style workflow, build first and then use the hardened launcher:

```bash
cd dashboard/frontend
npm ci
npm run build
cd ../..
python main.py dashboard
```

FastAPI serves the built SPA with deep-link fallback while preserving `/api`, `/docs`, and `/openapi.json`. The default bind is `127.0.0.1:8000`; an explicit public bind prints a warning because authentication is not implemented.

### Offline demo, backup, and integrity

Generate a fully synthetic case without Tor, provider keys, or Internet access:

```bash
python main.py demo create
```

Create and verify portable case backups, or audit a live case without modifying it:

```bash
python main.py case backup --case CASE-2026-0001 --output backups/
python main.py case backup-verify --file backups/CASE-2026-0001_TIMESTAMP.zip
python main.py case verify --case CASE-2026-0001
```

Backups contain a SHA-256 manifest, reject unsafe archive paths during verification, and exclude lock/temporary files and symlinks. Canonical JSON writes use atomic replacement and bounded cross-process locks.

### Docker

`docker compose up --build` builds the frontend and Python runtime, runs the final container as a non-root user, persists cases in a named volume, and publishes only `127.0.0.1:8000`. The container healthcheck uses `/api/v1/health`.

### Pages and analyst workflow

The persistent case workspace links Overview, Evidence, Indicators, Enrichment, Timeline, Relationship Graph, and Findings. The views provide compact summaries; metadata-only evidence tables; IOC and provider-claim filtering; paginated chronology; analyst-note entry; a Cytoscape graph with zoom, pan, fit, selection, filters, three layouts, provenance detail, and an accessible table fallback; and local analyst findings. Loading, failure, and empty states are explicit.

The API is rooted at `/api/v1`. It provides case list/detail/overview and bounded local search; paginated evidence, indicators, enrichment, and timeline records; graph data, node detail, and bounded paths; plus the three deliberate local writes: analyst timeline notes, analyst graph nodes, and analyst graph edges. Page limits are validated, graph rendering is capped at 5,000 nodes, node details cap connected relationships at 500, and path depth cannot exceed six.

### Local-only security model

Authentication is not implemented. The documented and configured default is `127.0.0.1`, not a public bind. CORS permits only the two local Vite origins and does not allow credentials. Case IDs are validated before filesystem access, responses omit arbitrary filesystem paths and evidence bodies, and normal page loads never contact enrichment providers. React renders case and artifact values as hostile text: collected HTML and provider-controlled markup are never injected into the DOM. API failures return structured messages without stack traces.

Do not expose this service to a network without a separately designed authentication, authorization, TLS, and deployment-hardening phase.

### Current dashboard limitations

This is a single-user workstation interface with no authentication, authorization, background refresh, or saved UI preferences. Search is case-local and bounded rather than indexed. Cytoscape is deferred to the graph route, and graph node rendering is guarded, but very dense edge sets may still require tighter filters. Findings are timeline-backed notes and do not yet have standalone edit/delete or structured relationship fields. No AI attribution, autonomous crawling, threat scoring, or automatic actor identification is included.

## Implemented investigation flow

DarkIntel implements the following local investigation flow:

```text
IOC extraction
→ evidence enrichment
→ investigation timeline
→ relationship graph
→ CTI dashboard
```

The next step is a maintainer-led final security and engineering review, not another feature phase.

## Upstream attribution

DarkIntel was historically inspired by the [DarkFox project by Aryan Guenthner](https://github.com/aryanguenthner/darkfox). Its current release implementation is maintained independently, and upstream source artifacts are excluded. This attribution does not imply upstream endorsement or claim authorship of the upstream work.

## License status — release blocker

The upstream README historically states GPL-3.0 and links to `LICENSE`, but this repository snapshot contains no authoritative root `LICENSE` or `COPYING` file. No license text has been invented or added. Redistribution, relicensing, and public release remain blocked pending an authoritative upstream-license review.
