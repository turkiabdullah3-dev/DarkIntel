from darkintel.cases import CaseStore
from darkintel.utils import write_json
from main import main


def setup(tmp_path):
    store = CaseStore(tmp_path / "cases")
    case = store.create_case("CLI Timeline")
    root = store.root / case.case_id
    write_json(root / "extracted_iocs" / "indicators.json", {"indicators": [{
        "type": "domain", "value": "example.com", "normalized_value": "example.com",
        "first_seen": "2026-08-13T07:00:00Z", "source": "notes.txt",
    }]})
    return store, case


def args(store, *rest):
    return ["--cases-dir", str(store.root), "timeline", *rest]


def test_cli_build_show_filter_note_and_exports(tmp_path, capsys):
    store, case = setup(tmp_path)
    assert main(args(store, "build", "--case", case.case_id)) == 0
    assert "Timeline built" in capsys.readouterr().out
    assert main(args(store, "show", "--case", case.case_id, "--type", "ioc_extracted",
                     "--object", "example.com", "--from", "2026-08-13T07:00:00Z",
                     "--to", "2026-08-13T07:00:00Z")) == 0
    shown = capsys.readouterr().out
    assert "IOC_EXTRACTED" in shown and "Events shown: 1" in shown
    assert main(args(store, "note", "--case", case.case_id, "--title", "Analyst observation",
                     "--description", "Confirmed publicly", "--timestamp", "2026-08-13T10:30:00+03:00")) == 0
    assert "Analyst note created" in capsys.readouterr().out
    for format_name in ("json", "csv", "markdown"):
        assert main(args(store, "export", "--case", case.case_id, "--format", format_name)) == 0
        assert "Timeline exported" in capsys.readouterr().out


def test_cli_rejects_bad_timestamp_and_path(tmp_path):
    store, case = setup(tmp_path)
    main(args(store, "build", "--case", case.case_id))
    assert main(args(store, "show", "--case", case.case_id, "--from", "not-time")) == 2
    assert main(args(store, "build", "--case", "../escape")) == 2
