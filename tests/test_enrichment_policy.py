import pytest

from darkintel.enrichment.policy import EnrichmentPolicy


def test_policy_defaults_are_local_only():
    policy = EnrichmentPolicy()
    assert policy.enabled_providers == ["local"]
    assert policy.allow_network is False
    assert policy.max_indicators_per_run == 50


def test_policy_deduplicates_providers_and_validates_limits():
    assert EnrichmentPolicy(enabled_providers=["local", "local"]).enabled_providers == ["local"]
    with pytest.raises(ValueError):
        EnrichmentPolicy(max_requests_per_provider=0)
