import csv
import json

from darkintel.cases import CaseStore
from darkintel.evidence import IOCStore
from darkintel.extractors.base import Candidate
from darkintel.extractors.extractor import IOCExtractor
from darkintel.models import ExtractionResult, IOC, IOCType
from main import main


def test_engine_deduplicates_and_captures_bounded_context():
    result = IOCExtractor(context_chars=10).extract("prefix Example.COM then example.com suffix", "evidence-1")
    domains = [item for item in result.indicators if item.type == IOCType.DOMAIN]
    assert len(domains) == 1
    assert domains[0].source == "evidence-1"
    assert len(domains[0].context) <= len("example.com") + 20


def test_empty_input_and_json_serialization():
    result = IOCExtractor().extract("", "empty")
    assert result.total_found == 0
    assert json.loads(json.dumps(result.to_dict()))["indicators"] == []


def test_input_and_ioc_limits_return_warnings():
    content = "one.example two.example three.example " + "x" * 100
    result = IOCExtractor(max_input_chars=80, max_iocs=2).extract(content)
    assert result.total_found == 2
    assert any("truncated" in error for error in result.errors)
    assert any("IOC limit" in error for error in result.errors)


def test_extractor_failure_isolation():
    class Broken:
        name = "broken"

        def extract(self, content):
            raise RuntimeError("synthetic failure")

    class Working:
        name = "working"

        def extract(self, content):
            return [Candidate(IOCType.CVE, "CVE-2024-1234", "CVE-2024-1234", 0, 13, 1.0)]

    result = IOCExtractor([Broken(), Working()]).extract("CVE-2024-1234")
    assert result.total_found == 1
    assert "synthetic failure" in result.errors[0]


def test_case_level_deduplication_json_and_csv(tmp_path):
    case = CaseStore(tmp_path).create_case("IOC Case")
    store = IOCStore(tmp_path)
    first = ExtractionResult("one", [IOC(IOCType.DOMAIN, "Example.COM", "example.com", source="one")])
    second = ExtractionResult("two", [IOC(IOCType.DOMAIN, "example.com", "example.com", source="two")])
    store.merge(case.case_id, first)
    merged = store.merge(case.case_id, second)
    assert len(merged) == 1
    assert merged[0].observation_count == 2
    assert merged[0].sources == ["one", "two"]
    directory = tmp_path / case.case_id / "extracted_iocs"
    payload = json.loads((directory / "indicators.json").read_text(encoding="utf-8"))
    assert payload["total_unique"] == 1
    with (directory / "indicators.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["normalized_value"] == "example.com"
    assert rows[0]["observation_count"] == "2"


def test_cli_extracts_malformed_html_without_scripts_or_network(tmp_path, capsys):
    case = CaseStore(tmp_path / "cases").create_case("HTML")
    evidence = tmp_path / "evidence.html"
    evidence.write_text("<html><script>evil.example</script><p>Contact analyst@example.com"
                        "<a href='HTTPS://Example.COM/path'>link", encoding="utf-8")
    exit_code = main(["--cases-dir", str(tmp_path / "cases"), "extract", "--case", case.case_id,
                      "--file", str(evidence)])
    assert exit_code == 0
    assert "IOC Extraction Complete" in capsys.readouterr().out
    payload = json.loads((tmp_path / "cases" / case.case_id / "extracted_iocs" / "indicators.json")
                         .read_text(encoding="utf-8"))
    values = {item["normalized_value"] for item in payload["indicators"]}
    assert "evil.example" not in values
    assert "analyst@example.com" in values
    assert "https://example.com/path" in values
