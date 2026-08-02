import dns.resolver

from app.models.schemas import EmailVerificationStatus
from app.services.email_verification.factory import get_email_verification_adapter
from app.services.email_verification.mock import MockEmailVerificationAdapter
from app.services.email_verification.production import ProductionEmailVerificationAdapter


async def test_mock_adapter_accepts_a_well_formed_address():
    result = await MockEmailVerificationAdapter().verify("ada@example.com")
    assert result.status == EmailVerificationStatus.VALID


async def test_mock_adapter_rejects_malformed_addresses():
    result = await MockEmailVerificationAdapter().verify("not-an-email")
    assert result.status == EmailVerificationStatus.INVALID


async def test_mock_adapter_rejects_its_fixed_denylist_domains():
    result = await MockEmailVerificationAdapter().verify("someone@bounced.test")
    assert result.status == EmailVerificationStatus.INVALID


async def test_production_adapter_rejects_malformed_addresses_without_a_dns_lookup(monkeypatch):
    def _should_not_be_called(*a, **kw):
        raise AssertionError("DNS should not be queried for a malformed address")

    monkeypatch.setattr(dns.resolver, "resolve", _should_not_be_called)
    result = await ProductionEmailVerificationAdapter().verify("not-an-email")
    assert result.status == EmailVerificationStatus.INVALID


async def test_production_adapter_is_valid_when_mx_records_are_present(monkeypatch):
    monkeypatch.setattr(dns.resolver, "resolve", lambda domain, kind: ["mx1.example.com"])
    result = await ProductionEmailVerificationAdapter().verify("ada@example.com")
    assert result.status == EmailVerificationStatus.VALID


async def test_production_adapter_is_invalid_when_domain_has_no_mail_exchanger(monkeypatch):
    def _raise_nxdomain(domain, kind):
        raise dns.resolver.NXDOMAIN()

    monkeypatch.setattr(dns.resolver, "resolve", _raise_nxdomain)
    result = await ProductionEmailVerificationAdapter().verify("ada@nonexistent-domain-xyz.invalid")
    assert result.status == EmailVerificationStatus.INVALID


async def test_production_adapter_is_unknown_when_the_lookup_itself_fails(monkeypatch):
    def _raise_timeout(domain, kind):
        raise dns.resolver.LifetimeTimeout()

    monkeypatch.setattr(dns.resolver, "resolve", _raise_timeout)
    result = await ProductionEmailVerificationAdapter().verify("ada@example.com")
    assert result.status == EmailVerificationStatus.UNKNOWN


def test_factory_selects_mock_when_use_mock_clients_is_enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", True)
    assert isinstance(get_email_verification_adapter(), MockEmailVerificationAdapter)


def test_factory_selects_production_by_default(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "USE_MOCK_CLIENTS", False)
    assert isinstance(get_email_verification_adapter(), ProductionEmailVerificationAdapter)
