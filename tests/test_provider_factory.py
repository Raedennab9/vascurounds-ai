from __future__ import annotations

import pytest

from vascurounds.case_urns import ACUTE_LIMB_ISCHEMIA_URNS
from vascurounds.conference.content import (
    conference_available_for_urn,
    load_conference,
)
from vascurounds.models import CaseAsset
from vascurounds.providers.base import ProviderStatus, ProviderUnavailableError
from vascurounds.providers.datahub import DataHubCaseProvider
from vascurounds.providers.factory import (
    DEFAULT_DATAHUB_GMS_URL,
    FallbackCaseProvider,
    InvalidDataHubConfigurationError,
    create_provider,
    parse_environment_boolean,
    validate_datahub_gms_url,
)
from vascurounds.providers.mock import MockCaseProvider


class UnavailableProvider:
    @property
    def fallback_active(self) -> bool:
        return False

    @property
    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_name="datahub",
            datahub_connected=False,
            fallback_used=False,
            required_connection_failed=False,
            status_message="DataHub is offline",
        )

    def list_cases(self) -> list[CaseAsset]:
        raise ProviderUnavailableError("DataHub is offline")


def test_provider_defaults_to_real_datahub() -> None:
    provider = create_provider({})

    assert isinstance(provider, DataHubCaseProvider)
    assert DEFAULT_DATAHUB_GMS_URL == "http://localhost:8080"
    assert provider.required_urns == ACUTE_LIMB_ISCHEMIA_URNS


def test_mock_mode_supports_offline_development() -> None:
    provider = create_provider({"DATAHUB_MODE": "mock"})

    assert isinstance(provider, MockCaseProvider)
    assert len(provider.list_cases()) == 4
    assert provider.status.provider_name == "mock"
    assert provider.status.datahub_connected is False


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://localhost:8501",
        "https://example-codespace-8501.app.github.dev",
        "https://vascurounds-ai.streamlit.app",
        "https://share.streamlit.io/example/app",
    ],
)
def test_streamlit_url_is_rejected_as_datahub_gms_url(
    invalid_url: str,
) -> None:
    with pytest.raises(
        InvalidDataHubConfigurationError,
        match=r"Streamlit application.*http://localhost:8080",
    ):
        create_provider(
            {
                "DATAHUB_MODE": "real",
                "DATAHUB_GMS_URL": invalid_url,
            }
        )


@pytest.mark.parametrize(
    "valid_url",
    [
        "http://localhost:8080",
        "https://datahub.example.org",
        "https://metadata.example.org/gms",
    ],
)
def test_valid_local_and_remote_datahub_urls_are_accepted(
    valid_url: str,
) -> None:
    assert validate_datahub_gms_url(valid_url) == valid_url


@pytest.mark.parametrize(
    "invalid_url",
    [
        "",
        "localhost:8080",
        "not a url",
        "ftp://datahub.example.org",
        "https://",
        "https://user:password@datahub.example.org",
    ],
)
def test_malformed_or_unsafe_datahub_urls_fail_clearly(
    invalid_url: str,
) -> None:
    with pytest.raises(InvalidDataHubConfigurationError):
        create_provider(
            {
                "DATAHUB_MODE": "real",
                "DATAHUB_REQUIRED": "true",
                "DATAHUB_GMS_URL": invalid_url,
            }
        )


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_true_environment_boolean_values_are_parsed(value: str) -> None:
    assert (
        parse_environment_boolean(
            value,
            variable_name="DATAHUB_REQUIRED",
            default=False,
        )
        is True
    )


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off"])
def test_false_environment_boolean_values_are_parsed(value: str) -> None:
    assert (
        parse_environment_boolean(
            value,
            variable_name="DATAHUB_REQUIRED",
            default=True,
        )
        is False
    )


def test_invalid_environment_boolean_fails_clearly() -> None:
    with pytest.raises(
        InvalidDataHubConfigurationError,
        match="DATAHUB_REQUIRED must be one of",
    ):
        create_provider(
            {
                "DATAHUB_MODE": "real",
                "DATAHUB_REQUIRED": "sometimes",
            }
        )


def test_required_real_mode_never_constructs_a_fallback_provider() -> None:
    provider = create_provider(
        {
            "DATAHUB_MODE": "real",
            "DATAHUB_REQUIRED": "true",
            "DATAHUB_GMS_URL": "http://localhost:8080",
        }
    )

    assert isinstance(provider, DataHubCaseProvider)
    assert not isinstance(provider, FallbackCaseProvider)
    assert provider.required_urns == ACUTE_LIMB_ISCHEMIA_URNS


def test_auto_mode_with_fallback_allowed_constructs_fallback_provider() -> None:
    provider = create_provider(
        {
            "DATAHUB_MODE": "auto",
            "DATAHUB_REQUIRED": "false",
        }
    )

    assert isinstance(provider, FallbackCaseProvider)


def test_required_auto_mode_cannot_silently_fallback() -> None:
    provider = create_provider(
        {
            "DATAHUB_MODE": "auto",
            "DATAHUB_REQUIRED": "true",
        }
    )

    assert isinstance(provider, DataHubCaseProvider)
    assert provider.required_urns == ACUTE_LIMB_ISCHEMIA_URNS


def test_required_mock_mode_is_rejected_as_contradictory() -> None:
    with pytest.raises(
        InvalidDataHubConfigurationError,
        match="cannot be combined",
    ):
        create_provider(
            {
                "DATAHUB_MODE": "mock",
                "DATAHUB_REQUIRED": "true",
            }
        )


def test_fallback_provider_uses_safe_mock_cases_when_primary_is_unavailable() -> None:
    provider = FallbackCaseProvider(
        primary=UnavailableProvider(),
        fallback=MockCaseProvider(),
    )

    cases = provider.list_cases()

    assert provider.fallback_active is True
    assert provider.status.provider_name == "mock"
    assert provider.status.datahub_connected is False
    assert provider.status.fallback_used is True
    assert provider.status.required_connection_failed is False
    assert len(cases) == 4
    assert all(case.synthetic_data and case.educational_use for case in cases)
    assert all(conference_available_for_urn(case.urn) for case in cases)
    assert [load_conference(case).total_points for case in cases] == [100] * 4


def test_canonical_mock_urns_do_not_imply_datahub_connectivity() -> None:
    provider = MockCaseProvider()

    assert tuple(case.urn for case in provider.list_cases()) == (
        ACUTE_LIMB_ISCHEMIA_URNS
    )
    assert provider.status.datahub_connected is False
