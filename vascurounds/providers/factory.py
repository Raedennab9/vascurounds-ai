from __future__ import annotations

from collections.abc import Mapping
import os
from urllib.parse import urlparse

from vascurounds.models import CaseAsset
from vascurounds.providers.base import CaseProvider, ProviderUnavailableError
from vascurounds.providers.datahub import DataHubCaseProvider
from vascurounds.providers.mock import MockCaseProvider


DEFAULT_DATAHUB_GMS_URL = "http://localhost:8080"
DEFAULT_DATAHUB_MODE = "real"


class InvalidDataHubConfigurationError(ValueError):
    """Raised when DataHub configuration points to the Streamlit application."""


def validate_datahub_gms_url(gms_url: str) -> str:
    normalized_url = gms_url.strip()
    parsed_url = urlparse(normalized_url)
    hostname = (parsed_url.hostname or "").casefold()

    try:
        explicit_port = parsed_url.port
    except ValueError as exc:
        raise InvalidDataHubConfigurationError(
            f"DATAHUB_GMS_URL is not a valid URL: {normalized_url!r}."
        ) from exc

    codespaces_streamlit_url = (
        hostname == "8501.app.github.dev"
        or hostname.endswith("-8501.app.github.dev")
    )
    if explicit_port == 8501 or codespaces_streamlit_url:
        raise InvalidDataHubConfigurationError(
            "DATAHUB_GMS_URL appears to point to the Streamlit application "
            "on port 8501. Set it to the internal DataHub GMS endpoint "
            "http://localhost:8080."
        )

    return normalized_url


class FallbackCaseProvider:
    def __init__(self, primary: CaseProvider, fallback: CaseProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self._fallback_active = False

    @property
    def fallback_active(self) -> bool:
        return self._fallback_active

    def list_cases(self) -> list[CaseAsset]:
        try:
            cases = self._primary.list_cases()
            self._fallback_active = False
            return cases
        except ProviderUnavailableError:
            self._fallback_active = True
            return self._fallback.list_cases()


def create_provider(
    environ: Mapping[str, str] | None = None,
) -> CaseProvider:
    environment = os.environ if environ is None else environ
    gms_url = validate_datahub_gms_url(
        environment.get("DATAHUB_GMS_URL", DEFAULT_DATAHUB_GMS_URL)
    )
    mode = environment.get("DATAHUB_MODE", DEFAULT_DATAHUB_MODE).strip().casefold()

    if mode == "real":
        return DataHubCaseProvider(gms_url)
    if mode == "mock":
        return MockCaseProvider()
    if mode == "auto":
        return FallbackCaseProvider(
            primary=DataHubCaseProvider(gms_url),
            fallback=MockCaseProvider(),
        )

    raise ValueError(
        "DATAHUB_MODE must be one of: real, mock, auto "
        f"(received {mode!r})."
    )
