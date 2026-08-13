from darkintel.extractors.identities import IdentityExtractor
from darkintel.models import IOCType


def test_email_extraction_and_domain_normalization():
    found = IdentityExtractor().extract("Contact Analyst.Name+CTI@Example.COM")
    email = next(item for item in found if item.type == IOCType.EMAIL)
    assert email.normalized_value == "Analyst.Name+CTI@example.com"


def test_telegram_forms_normalize_and_invalid_is_ignored():
    found = IdentityExtractor().extract("@ExampleUser t.me/ExampleUser telegram.me/Other_User @abc")
    telegram = [item.normalized_value for item in found if item.type == IOCType.TELEGRAM]
    assert telegram == ["@exampleuser", "@exampleuser", "@other_user"]


def test_email_is_not_also_telegram():
    found = IdentityExtractor().extract("analyst@example.com")
    assert not [item for item in found if item.type == IOCType.TELEGRAM]
