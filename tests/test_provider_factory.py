from __future__ import annotations

from vascurounds.models import CaseAsset
from vascurounds.providers.base import ProviderUnavailableError
from vascurounds.providers.datahub import DataHubCaseProvider
from vascurounds.providers.factory import (
    DEFAULT_DATAHUB_GMS_URL,
    FallbackCaseProvider,
    create_provider,
)
from vascurounds.providers.mock import MockCaseProvider


class UnavailableProvider:
    @property
    def fallback_active(self) -> bool:
        return False

    def list_cases(self) -> list[CaseAsset]:
        raise ProviderUnavailableError("DataHub is offline")


def test_provider_defaults_to_real_datahub() -> None:
    provider = create_provider({})

    assert isinstance(provider, DataHubCaseProvider)
    assert DEFAULT_DATAHUB_GMS_URL == "http://localhost:8080"


def test_mock_mode_supports_offline_development() -> None:
    provider = create_provider({"DATAHUB_MODE": "mock"})

    assert isinstance(provider, MockCaseProvider)
    assert len(provider.list_cases()) == 4


def test_fallback_provider_uses_safe_mock_cases_when_primary_is_unavailable() -> None:
    provider = FallbackCaseProvider(
        primary=UnavailableProvider(),
        fallback=MockCaseProvider(),
    )

    cases = provider.list_cases()

    assert provider.fallback_active is True
    assert len(cases) == 4
    assert all(case.synthetic_data and case.educational_use for case in cases)
