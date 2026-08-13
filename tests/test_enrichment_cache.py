from datetime import timedelta

from darkintel.cases import CaseStore
from darkintel.enrichment.cache import EnrichmentCache
from darkintel.models import EnrichmentRecord, utc_now
from darkintel.utils import write_json


def make_record(provider="local"):
    return EnrichmentRecord(provider, "domain", "Example.COM", "example.com", success=True)


def test_cache_hit_and_provider_isolation(tmp_path):
    case = CaseStore(tmp_path).create_case("Cache")
    cache = EnrichmentCache(tmp_path, case.case_id)
    cache.put(make_record(), 24)
    hit = cache.get("local", "domain", "example.com")
    assert hit and hit.cached
    assert cache.get("rdap", "domain", "example.com") is None


def test_expired_cache_is_not_returned(tmp_path):
    case = CaseStore(tmp_path).create_case("Cache")
    cache = EnrichmentCache(tmp_path, case.case_id)
    record = make_record()
    record.expires_at = utc_now() - timedelta(seconds=1)
    path = cache.directory / f"{cache.key('local', 'domain', 'example.com')}.json"
    write_json(path, record.to_dict())
    assert cache.get("local", "domain", "example.com") is None


def test_failed_records_receive_shorter_ttl(tmp_path):
    case = CaseStore(tmp_path).create_case("Cache")
    cache = EnrichmentCache(tmp_path, case.case_id)
    record = EnrichmentRecord("rdap", "domain", "x.test", "x.test", success=False,
                              error="not found", error_category="not_found")
    before = utc_now()
    cache.put(record, 24)
    assert record.expires_at <= before + timedelta(hours=1, seconds=1)
