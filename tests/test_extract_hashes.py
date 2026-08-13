import pytest

from darkintel.extractors.hashes import HashExtractor
from darkintel.models import IOCType


@pytest.mark.parametrize("indicator_type,length", [
    (IOCType.MD5, 32), (IOCType.SHA1, 40), (IOCType.SHA256, 64), (IOCType.SHA512, 128),
])
def test_exact_hash_lengths_and_normalization(indicator_type, length):
    raw = "A" * length
    found = [item for item in HashExtractor().extract(f"hash={raw}") if item.type == indicator_type]
    assert len(found) == 1
    assert found[0].normalized_value == raw.lower()


def test_hash_rejects_embedded_or_wrong_length_hex():
    assert HashExtractor().extract("f" * 31 + " " + "a" * 129) == []
