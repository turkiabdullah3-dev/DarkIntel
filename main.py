"""DarkIntel command-line interface."""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
from pathlib import Path
import sys
from typing import cast

from bs4 import BeautifulSoup

from darkintel.cases import CaseStore
from darkintel.evidence import EvidenceStore, IOCStore
from darkintel.enrichment import EnrichmentManager, EnrichmentPolicy
from darkintel.enrichment.providers import (AbuseIPDBProvider, LocalProvider, RDAPProvider,
                                             VirusTotalProvider)
from darkintel.extractors import IOCExtractor
from darkintel.extractors.extractor import DEFAULT_MAX_INPUT_CHARS
from darkintel.graph import (GraphNodeType, GraphQuery, GraphRelationship, GraphStore,
                             RelationshipGraphBuilder)
from darkintel.tor import check_tor
from darkintel.timeline import TimelineBuilder, TimelineEventType, TimelineStore
from darkintel.verifier import OnionVerifier
from darkintel.maintenance import backup_case, verify_backup, verify_case
from darkintel.version import __version__
from darkintel.demo import create_demo
from darkintel.release import export_release_tree

LOGGER = logging.getLogger("darkintel")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DarkIntel — CTI & OSINT Investigation Platform")
    parser.add_argument("--cases-dir", default=os.environ.get("DARKINTEL_CASES_DIR", "cases"),
                        help="case storage directory (default: DARKINTEL_CASES_DIR or cases)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"DarkIntel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    tor = sub.add_parser("tor-check", help="test a Tor SOCKS listener")
    _add_tor_options(tor)

    verify = sub.add_parser("verify", help="verify one Tor v3 onion URL")
    verify.add_argument("--url", required=True)
    _add_tor_options(verify, request_timeout=True)

    investigate = sub.add_parser("investigate", help="verify onion URLs from a file and save results")
    investigate.add_argument("--case", required=True, dest="case_id")
    investigate.add_argument("--input", required=True, type=Path)
    _add_tor_options(investigate, request_timeout=True)

    extract = sub.add_parser("extract", help="extract IOCs from already-collected local evidence")
    extract.add_argument("--case", required=True, dest="case_id")
    extract.add_argument("--file", required=True, type=Path)
    extract.add_argument("--format", choices=["summary", "json"], default="summary")

    enrich = sub.add_parser("enrich", help="enrich extracted case IOCs using explicit providers")
    enrich.add_argument("--case", required=True, dest="case_id")
    enrich.add_argument("--provider", action="append", required=True,
                        choices=["local", "rdap", "virustotal", "abuseipdb"])
    enrich.add_argument("--allow-network", action="store_true",
                        help="explicitly permit selected network providers to receive normalized IOCs")
    enrich.add_argument("--limit", type=int, default=50)

    timeline = sub.add_parser("timeline", help="build and inspect the derived case timeline")
    timeline_sub = timeline.add_subparsers(dest="timeline_command", required=True)
    timeline_build = timeline_sub.add_parser("build")
    timeline_build.add_argument("--case", required=True, dest="case_id")
    timeline_show = timeline_sub.add_parser("show")
    timeline_show.add_argument("--case", required=True, dest="case_id")
    timeline_show.add_argument("--type", choices=[item.value for item in TimelineEventType])
    timeline_show.add_argument("--object")
    timeline_show.add_argument("--object-type")
    timeline_show.add_argument("--source")
    timeline_show.add_argument("--from", dest="from_time")
    timeline_show.add_argument("--to", dest="to_time")
    timeline_export = timeline_sub.add_parser("export")
    timeline_export.add_argument("--case", required=True, dest="case_id")
    timeline_export.add_argument("--format", choices=["json", "csv", "markdown"], required=True)
    timeline_note = timeline_sub.add_parser("note")
    timeline_note.add_argument("--case", required=True, dest="case_id")
    timeline_note.add_argument("--title", required=True)
    timeline_note.add_argument("--description")
    timeline_note.add_argument("--timestamp")
    timeline_note.add_argument("--tag", action="append", default=[])

    graph = sub.add_parser("graph", help="build and query the derived relationship graph")
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)
    graph_build = graph_sub.add_parser("build")
    graph_build.add_argument("--case", required=True, dest="case_id")
    graph_show = graph_sub.add_parser("show")
    graph_show.add_argument("--case", required=True, dest="case_id")
    graph_nodes = graph_sub.add_parser("nodes")
    graph_nodes.add_argument("--case", required=True, dest="case_id")
    graph_nodes.add_argument("--type", choices=[item.value for item in GraphNodeType])
    graph_neighbors = graph_sub.add_parser("neighbors")
    graph_neighbors.add_argument("--case", required=True, dest="case_id")
    graph_neighbors.add_argument("--node", required=True)
    graph_path = graph_sub.add_parser("path")
    graph_path.add_argument("--case", required=True, dest="case_id")
    graph_path.add_argument("--from", required=True, dest="source_node")
    graph_path.add_argument("--to", required=True, dest="target_node")
    graph_path.add_argument("--max-depth", type=int, default=4)
    graph_export = graph_sub.add_parser("export")
    graph_export.add_argument("--case", required=True, dest="case_id")
    graph_export.add_argument("--format", choices=["json", "graphml", "cytoscape"], required=True)
    graph_node = graph_sub.add_parser("node")
    graph_node_sub = graph_node.add_subparsers(dest="graph_node_command", required=True)
    graph_node_add = graph_node_sub.add_parser("add")
    graph_node_add.add_argument("--case", required=True, dest="case_id")
    graph_node_add.add_argument("--type", required=True,
                                choices=["analyst_entity", "threat_actor", "organization"])
    graph_node_add.add_argument("--value", required=True)
    graph_node_add.add_argument("--label", required=True)
    graph_edge = graph_sub.add_parser("edge")
    graph_edge_sub = graph_edge.add_subparsers(dest="graph_edge_command", required=True)
    graph_edge_add = graph_edge_sub.add_parser("add")
    graph_edge_add.add_argument("--case", required=True, dest="case_id")
    graph_edge_add.add_argument("--source", required=True)
    graph_edge_add.add_argument("--target", required=True)
    graph_edge_add.add_argument("--relationship", required=True,
                                choices=[item.value for item in GraphRelationship])
    graph_edge_add.add_argument("--confidence", type=float, default=0.75)

    case = sub.add_parser("case", help="manage investigation cases")
    case_sub = case.add_subparsers(dest="case_command", required=True)
    create = case_sub.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--description", default="")
    create.add_argument("--tag", action="append", default=[])
    show = case_sub.add_parser("show")
    show.add_argument("case_id")
    case_sub.add_parser("list")
    update = case_sub.add_parser("update")
    update.add_argument("case_id")
    update.add_argument("--name")
    update.add_argument("--description")
    update.add_argument("--status", choices=["open", "closed", "archived"])
    update.add_argument("--tag", action="append", dest="tags")
    close = case_sub.add_parser("close")
    close.add_argument("case_id")
    backup = case_sub.add_parser("backup")
    backup.add_argument("--case", required=True, dest="case_id")
    backup.add_argument("--output", required=True, type=Path)
    backup_verify = case_sub.add_parser("backup-verify")
    backup_verify.add_argument("--file", required=True, type=Path)
    case_verify = case_sub.add_parser("verify")
    case_verify.add_argument("--case", required=True, dest="case_id")

    dashboard = sub.add_parser("dashboard", help="serve the local API and built dashboard")
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", default=8000, type=int)
    demo = sub.add_parser("demo", help="manage fully synthetic offline demo data")
    demo_sub = demo.add_subparsers(dest="demo_command", required=True)
    demo_sub.add_parser("create")
    release_tree = sub.add_parser("release-tree", help="export an allowlisted independent release tree")
    release_sub = release_tree.add_subparsers(dest="release_command", required=True)
    release_export = release_sub.add_parser("export")
    release_export.add_argument("--output", required=True, type=Path)
    return parser


def _add_tor_options(parser: argparse.ArgumentParser, request_timeout: bool = False) -> None:
    parser.add_argument("--tor-host", default="127.0.0.1")
    parser.add_argument("--tor-port", default=9050, type=int)
    parser.add_argument("--timeout", default=15.0 if request_timeout else 1.0, type=float)


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _case_command(args: argparse.Namespace, store: CaseStore) -> int:
    if args.case_command == "create":
        case = store.create_case(args.name, args.description, args.tag)
    elif args.case_command == "show":
        case = store.load_case(args.case_id)
    elif args.case_command == "list":
        _print([case.to_dict() for case in store.list_cases()])
        return 0
    elif args.case_command == "update":
        case = store.update_case(args.case_id, name=args.name, description=args.description,
                                 status=args.status, tags=args.tags)
    elif args.case_command == "backup":
        print(f"Backup created: {backup_case(store.root, args.case_id, args.output)}")
        return 0
    elif args.case_command == "backup-verify":
        result = verify_backup(args.file)
        _print(result)
        return 0 if result["valid"] else 1
    elif args.case_command == "verify":
        result = verify_case(store.root, args.case_id)
        _print(result)
        return 0 if result["valid"] else 1
    else:
        case = store.close_case(args.case_id)
    _print(case.to_dict())
    return 0


def _investigate(args: argparse.Namespace, store: CaseStore) -> int:
    store.load_case(args.case_id)
    if not args.input.is_file():
        raise FileNotFoundError(f"input file not found: {args.input}")
    verifier = OnionVerifier(args.tor_host, args.tor_port, args.timeout)
    evidence = EvidenceStore(store.root)
    total = live = failed = 0
    for line in args.input.read_text(encoding="utf-8-sig").splitlines():
        target = line.strip()
        if not target or target.startswith("#"):
            continue
        total += 1
        result = verifier.verify(target)
        evidence.save_result(args.case_id, result)
        if result.is_live:
            live += 1
        else:
            failed += 1
        print(f"{target}: {'reachable' if result.is_live else result.error}")
    LOGGER.info("investigation completed: case=%s total=%d", args.case_id, total)
    _print({"case_id": args.case_id, "processed": total, "reachable": live, "failed": failed})
    return 0 if failed == 0 else 1


def _read_evidence(path: Path) -> tuple[str, list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"evidence file not found: {path}")
    max_bytes = DEFAULT_MAX_INPUT_CHARS * 4
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    warnings = []
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
        warnings.append(f"Evidence file truncated at {max_bytes} bytes")
    text = raw.decode("utf-8", errors="replace")
    is_html = path.suffix.lower() in {".html", ".htm"} or "<html" in text[:1000].lower()
    if not is_html:
        return text, warnings
    soup = BeautifulSoup(text, "html.parser")
    for element in soup(["script", "style", "noscript", "template"]):
        element.decompose()
    hrefs = [anchor.get("href") for anchor in soup.find_all("a", href=True)]
    visible = soup.get_text(" ", strip=True)
    return visible + "\n" + "\n".join(str(href) for href in hrefs), warnings


def _extract(args: argparse.Namespace, store: CaseStore) -> int:
    store.load_case(args.case_id)
    content, warnings = _read_evidence(args.file)
    result = IOCExtractor().extract(content, source=str(args.file))
    result.errors[:0] = warnings
    case_indicators = IOCStore(store.root).merge(args.case_id, result)
    counts: dict[str, int] = {}
    for indicator in result.indicators:
        counts[indicator.type.value] = counts.get(indicator.type.value, 0) + 1
    if args.format == "json":
        _print(result.to_dict())
    else:
        print("IOC Extraction Complete\n")
        for indicator_type in sorted(counts):
            print(f"{indicator_type.upper():12} {counts[indicator_type]}")
        print(f"\nUnique in this file: {result.total_found}")
        print(f"Total unique in case: {len(case_indicators)}")
        if result.errors:
            print(f"Warnings: {len(result.errors)}")
    LOGGER.info("IOC extraction completed: case=%s source=%s unique=%d", args.case_id, args.file,
                result.total_found)
    return 0


def _enrich(args: argparse.Namespace, store: CaseStore) -> int:
    store.load_case(args.case_id)
    if args.limit < 1:
        raise ValueError("enrichment limit must be positive")
    policy = EnrichmentPolicy(enabled_providers=args.provider, allow_network=args.allow_network,
                              max_indicators_per_run=min(args.limit, 50))
    providers = [LocalProvider(), RDAPProvider(), VirusTotalProvider(), AbuseIPDBProvider()]
    manager = EnrichmentManager(providers, policy, root=store.root, case_id=args.case_id)
    selected_providers = policy.enabled_providers
    _, summary = manager.enrich_case(providers=selected_providers, limit=args.limit)
    print("Enrichment Complete\n")
    print(f"Indicators processed: {summary['indicators_processed']}")
    for name in selected_providers:
        provider_stats = cast(dict[str, object], summary["providers"])
        stats = cast(dict[str, int], provider_stats.get(name, {}))
        print(f"{name:14} {stats.get('success', 0)} success / {stats.get('failed', 0)} failed / "
              f"{stats.get('cached', 0)} cached / {stats.get('unsupported', 0)} unsupported")
    print(f"\nNetwork requests: {summary['network_requests']}")
    print(f"Cache hits: {summary['cache_hits']}")
    print(f"Warnings: {summary['warnings']}")
    return 0


def _timeline(args: argparse.Namespace, store: CaseStore) -> int:
    store.load_case(args.case_id)
    timeline_store = TimelineStore(store.root)
    if args.timeline_command == "build":
        events = TimelineBuilder(store.root).build_case_timeline(args.case_id)
        print(f"Timeline built: {len(events)} events")
        return 0
    if args.timeline_command == "note":
        note = timeline_store.add_note(args.case_id, args.title, args.description, args.timestamp, args.tag)
        print(f"Analyst note created: {note.event_id}")
        return 0
    if args.timeline_command == "export":
        path = timeline_store.export(args.case_id, args.format)
        print(f"Timeline exported: {path}")
        return 0
    events = timeline_store.filter(args.case_id, event_type=args.type, object_value=args.object,
                                   object_type=args.object_type, from_time=args.from_time,
                                   to_time=args.to_time, source=args.source)
    print(f"Investigation Timeline\n{args.case_id}\n")
    for event in events:
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%SZ")
        print(f"{timestamp}  {event.event_type.value.upper()}")
        detail = event.title
        if event.object_type and event.object_value:
            detail += f" — {event.object_type}: {event.object_value}"
        print(f"  {detail}\n")
    print(f"Events shown: {len(events)}")
    return 0


def _graph(args: argparse.Namespace, store: CaseStore) -> int:
    store.load_case(args.case_id)
    graph_store = GraphStore(store.root)
    if args.graph_command == "build":
        result = RelationshipGraphBuilder(store.root).build_case_graph(args.case_id)
        print(f"Graph built: {len(result.nodes)} nodes / {len(result.edges)} edges")
        return 0
    if args.graph_command == "node":
        node = graph_store.add_node(args.case_id, args.type, args.value, args.label)
        print(f"Manual node created: {node.node_id}")
        return 0
    if args.graph_command == "edge":
        edge = graph_store.add_edge(args.case_id, args.source, args.target, args.relationship, args.confidence)
        print(f"Manual edge created: {edge.edge_id}")
        return 0
    if args.graph_command == "export":
        print(f"Graph exported: {graph_store.export(args.case_id, args.format)}")
        return 0
    result = graph_store.load(args.case_id)
    query = GraphQuery(result.nodes, result.edges)
    if args.graph_command == "nodes":
        nodes = query.nodes_by_type(args.type) if args.type else sorted(result.nodes, key=lambda node: node.node_id)
        for node in nodes:
            print(f"{node.node_id}  {node.node_type.value:18} {node.label}")
        print(f"Nodes shown: {len(nodes)}")
        return 0
    if args.graph_command == "neighbors":
        nodes = query.neighbors(args.node)
        for node in nodes:
            print(f"{node.node_id}  {node.node_type.value:18} {node.label}")
        print(f"Neighbors: {len(nodes)}")
        return 0
    if args.graph_command == "path":
        nodes = query.path_between(args.source_node, args.target_node, args.max_depth)
        print(" -> ".join(node.node_id for node in nodes) if nodes else "No path found")
        return 0
    summary = graph_store.summary(result)
    print(f"Relationship Graph\n{args.case_id}\n")
    print(f"Nodes: {summary['total_nodes']}\nEdges: {summary['total_edges']}\n")
    print("Node types:")
    for kind, count in cast(dict[str, int], summary["node_types"]).items():
        print(f"  {kind:20} {count}")
    print("\nRelationships:")
    for relationship, count in cast(dict[str, int], summary["relationship_types"]).items():
        print(f"  {relationship:20} {count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if args.command == "dashboard":
            if not 1 <= args.port <= 65535:
                raise ValueError("dashboard port must be between 1 and 65535")
            try:
                public_bind = ipaddress.ip_address(args.host).is_unspecified
            except ValueError:
                public_bind = False
            if public_bind:
                LOGGER.warning("Dashboard is being exposed beyond loopback; authentication is not implemented.")
            cases_root = Path(args.cases_dir)
            cases_root.mkdir(parents=True, exist_ok=True)
            if not cases_root.is_dir():
                raise OSError("cases directory is not accessible")
            frontend = Path(__file__).parent / "dashboard" / "frontend" / "dist" / "index.html"
            if not frontend.is_file():
                raise FileNotFoundError("frontend build missing; run npm ci and npm run build in dashboard/frontend")
            import uvicorn
            uvicorn.run("dashboard.backend.app:app", host=args.host, port=args.port)
            return 0
        if args.command == "demo":
            case_id = create_demo(Path(args.cases_dir))
            print(f"Synthetic demo ready: {case_id}")
            return 0
        if args.command == "release-tree":
            result = export_release_tree(Path(__file__).parent, args.output)
            _print(result)
            return 0
        if args.command == "tor-check":
            status = check_tor(args.tor_host, args.tor_port, args.timeout)
            LOGGER.info("Tor availability check: %s", status.available)
            _print(status.to_dict())
            return 0 if status.available else 1
        if args.command == "verify":
            result = OnionVerifier(args.tor_host, args.tor_port, args.timeout).verify(args.url)
            _print(result.to_dict())
            return 0 if result.is_live else 1
        store = CaseStore(args.cases_dir)
        if args.command == "case":
            return _case_command(args, store)
        if args.command == "extract":
            return _extract(args, store)
        if args.command == "enrich":
            return _enrich(args, store)
        if args.command == "timeline":
            return _timeline(args, store)
        if args.command == "graph":
            return _graph(args, store)
        return _investigate(args, store)
    except (ValueError, FileNotFoundError, OSError) as exc:
        LOGGER.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
