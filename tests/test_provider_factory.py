from __future__ import annotations

import pytest

from vascurounds.conference.content import (
    conference_available_for_urn,
    load_conference,
)
from vascurounds.models import CaseAsset
from vascurounds.providers.base import ProviderUnavailableError
from vascurounds.providers.datahub import DataHubCaseProvider
from vascurounds.providers.factory import (
    DEFAULT_DATAHUB_GMS_URL,
    FallbackCaseProvider,
    InvalidDataHubConfigurationError,
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


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://localhost:8501",
        "https://example-codespace-8501.app.github.dev",
    ],
)
def test_streamlit_url_is_rejected_as_datahub_gms_url(
    invalid_url: str,
) -> None:
    with pytest.raises(
        InvalidDataHubConfigurationError,
        match=r"Streamlit application on port 8501.*http://localhost:8080",
    ):
        create_provider(
            {
                "DATAHUB_MODE": "real",
                "DATAHUB_GMS_URL": invalid_url,
            }
        )


def test_fallback_provider_uses_safe_mock_cases_when_primary_is_unavailable() -> None:
    provider = FallbackCaseProvider(
        primary=UnavailableProvider(),
        fallback=MockCaseProvider(),
    )

    cases = provider.list_cases()

    assert provider.fallback_active is True
    assert len(cases) == 4
    assert all(case.synthetic_data and case.educational_use for case in cases)
    assert all(conference_available_for_urn(case.urn) for case in cases)
    assert [load_conference(case).total_points for case in cases] == [100] * 4
