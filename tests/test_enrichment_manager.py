import json

from darkintel.cases import CaseStore
from darkintel.enrichment.base import EnrichmentProvider
from darkintel.enrichment.manager import EnrichmentManager
from darkintel.enrichment.policy import EnrichmentPolicy
from darkintel.enrichment.providers.local import LocalProvider
from darkintel.evidence import IOCStore
from darkintel.models import EnrichmentRecord, ExtractionResult, IOC, IOCType
from main import main


class FakeNetworkProvider(EnrichmentProvider):
    name = "rdap"
    supported_types = frozenset({"domain"})
    requires_network = True

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail
        self.received = []

    def enrich(self, indicator):
        self.calls += 1
        self.received.append(indicator)
        if self.fail:
            raise RuntimeError("provider exploded")
        return EnrichmentRecord(self.name, indicator.type.value, indicator.value,
                                indicator.normalized_value, success=True, summary={"registrar": "Example"})


def domain(value="example.com"):
    return IOC(IOCType.DOMAIN, value, value)


def prepare_case(tmp_path, indicators=None):
    store = CaseStore(tmp_path / "cases")
    case = store.create_case("Enrichment")
    IOCStore(store.root).merge(case.case_id, ExtractionResult("test", indicators or [domain()]))
    return store, case


def test_network_blocking_and_unsupported_never_call_provider():
    network = FakeNetworkProvider()
    policy = EnrichmentPolicy(enabled_providers=["rdap"], allow_network=False)
    result = EnrichmentManager([network], policy).enrich_indicator(domain())
    assert network.calls == 0
    assert result.records[0].error_category == "configuration_error"
    policy = EnrichmentPolicy(enabled_providers=["rdap"], allow_network=True)
    result = EnrichmentManager([network], policy).enrich_indicator(
        IOC(IOCType.EMAIL, "a@example.com", "a@example.com"))
    assert network.calls == 0
    assert result.records[0].error_category == "unsupported_indicator"


def test_network_provider_receives_only_minimal_indicator():
    network = FakeNetworkProvider()
    indicator = IOC(IOCType.DOMAIN, "Example.COM", "example.com", source="C:/private/evidence.txt",
                    context="analyst private notes", tags=["case-tag"], sources=["private-source"])
    manager = EnrichmentManager([network], EnrichmentPolicy(enabled_providers=["rdap"], allow_network=True))
    manager.enrich_indicator(indicator)
    sent = network.received[0]
    assert sent.value == "example.com"
    assert sent.source is None and sent.context is None and sent.tags == [] and sent.sources == []


def test_request_limit_and_failure_isolation():
    network = FakeNetworkProvider()
    manager = EnrichmentManager([network], EnrichmentPolicy(enabled_providers=["rdap"], allow_network=True,
                                                             max_requests_per_provider=1))
    assert manager.enrich_indicator(domain("one.test")).records[0].success
    limited = manager.enrich_indicator(domain("two.test"))
    assert limited.records[0].error_category == "rate_limited"
    broken = EnrichmentManager([FakeNetworkProvider(fail=True)],
                               EnrichmentPolicy(enabled_providers=["rdap"], allow_network=True))
    result = broken.enrich_indicator(domain())
    assert result.records[0].error_category == "provider_error"
    assert "provider exploded" not in result.records[0].error


def test_cache_hit_and_case_persistence(tmp_path):
    store, case = prepare_case(tmp_path)
    manager = EnrichmentManager([LocalProvider()], EnrichmentPolicy(), root=store.root, case_id=case.case_id)
    _, first_summary = manager.enrich_case()
    assert first_summary["indicators_processed"] == 1
    _, second_summary = manager.enrich_case()
    assert second_summary["cache_hits"] == 1
    enrichment = store.root / case.case_id / "enrichment"
    records = json.loads((enrichment / "records.json").read_text(encoding="utf-8"))
    assert len(records["results"]) == 2
    assert (enrichment / "summary.json").is_file()
    assert (enrichment / "cache").is_dir()


def test_case_indicator_limit(tmp_path):
    store, case = prepare_case(tmp_path, [domain(f"d{i}.test") for i in range(3)])
    manager = EnrichmentManager([LocalProvider()], EnrichmentPolicy(max_indicators_per_run=2),
                                root=store.root, case_id=case.case_id)
    results, _ = manager.enrich_case(limit=3)
    assert len(results) == 2


def test_cli_local_and_network_blocked(tmp_path, capsys):
    store, case = prepare_case(tmp_path)
    assert main(["--cases-dir", str(store.root), "enrich", "--case", case.case_id,
                 "--provider", "local"]) == 0
    assert "Network requests: 0" in capsys.readouterr().out
    assert main(["--cases-dir", str(store.root), "enrich", "--case", case.case_id,
                 "--provider", "rdap"]) == 0
    blocked = capsys.readouterr().out
    assert "0 success / 1 failed" in blocked
    assert "Network requests: 0" in blocked


def test_cli_explicit_network_opt_in_with_mock_provider(tmp_path, capsys, monkeypatch):
    store, case = prepare_case(tmp_path)
    fake = FakeNetworkProvider()
    monkeypatch.setattr("main.RDAPProvider", lambda: fake)
    assert main(["--cases-dir", str(store.root), "enrich", "--case", case.case_id,
                 "--provider", "rdap", "--allow-network"]) == 0
    assert fake.calls == 1
    assert "1 success" in capsys.readouterr().out
