from darkintel.cases import CaseStore
from darkintel.graph.models import GraphNodeType
from darkintel.graph.store import GraphStore
from darkintel.utils import write_json
from main import main


def setup(tmp_path):
    store = CaseStore(tmp_path / "cases")
    case = store.create_case("CLI Graph")
    root = store.root / case.case_id
    write_json(root / "extracted_iocs" / "indicators.json", {"indicators": [
        {"type": "domain", "normalized_value": "example.com", "source": "notes.txt"},
    ]})
    return store, case


def args(store, *rest):
    return ["--cases-dir", str(store.root), "graph", *rest]


def test_cli_build_show_nodes_manual_neighbors_path_and_exports(tmp_path, capsys):
    store, case = setup(tmp_path)
    assert main(args(store, "build", "--case", case.case_id)) == 0
    assert "Graph built" in capsys.readouterr().out
    assert main(args(store, "show", "--case", case.case_id)) == 0
    assert "Relationship Graph" in capsys.readouterr().out
    assert main(args(store, "nodes", "--case", case.case_id, "--type", "domain")) == 0
    assert "example.com" in capsys.readouterr().out
    assert main(args(store, "node", "add", "--case", case.case_id, "--type", "threat_actor",
                     "--value", "Example Group", "--label", "Example Group")) == 0
    assert "Manual node created" in capsys.readouterr().out
    graph = GraphStore(store.root).load(case.case_id)
    actor = next(node for node in graph.nodes if node.node_type == GraphNodeType.THREAT_ACTOR)
    domain = next(node for node in graph.nodes if node.node_type == GraphNodeType.DOMAIN)
    assert main(args(store, "edge", "add", "--case", case.case_id, "--source", actor.node_id,
                     "--target", domain.node_id, "--relationship", "associated_with")) == 0
    capsys.readouterr()
    assert main(args(store, "neighbors", "--case", case.case_id, "--node", actor.node_id)) == 0
    assert "example.com" in capsys.readouterr().out
    assert main(args(store, "path", "--case", case.case_id, "--from", actor.node_id,
                     "--to", domain.node_id)) == 0
    assert " -> " in capsys.readouterr().out
    for format_name in ("json", "graphml", "cytoscape"):
        assert main(args(store, "export", "--case", case.case_id, "--format", format_name)) == 0
        assert "Graph exported" in capsys.readouterr().out


def test_cli_rejects_cross_case_or_missing_endpoint(tmp_path):
    store, case = setup(tmp_path)
    main(args(store, "build", "--case", case.case_id))
    assert main(args(store, "edge", "add", "--case", case.case_id,
                     "--source", "00000000-0000-0000-0000-000000000000",
                     "--target", "00000000-0000-0000-0000-000000000001",
                     "--relationship", "associated_with")) == 2
