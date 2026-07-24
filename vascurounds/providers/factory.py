from __future__ import annotations

from collections.abc import Mapping
import os
from urllib.parse import urlparse

from vascurounds.models import CaseAsset
from vascurounds.providers.base import (
    CaseProvider,
    ProviderStatus,
    ProviderUnavailableError,
)
from vascurounds.providers.datahub import (
    DataHubCaseProvider,
    required_datahub_provider,
)
from vascurounds.providers.mock import MockCaseProvider


DEFAULT_DATAHUB_GMS_URL = "http://localhost:8080"
DEFAULT_DATAHUB_MODE = "real"
_TRUE_VALUES = {"true", "1", "yes", "on"}
_FALSE_VALUES = {"false", "0", "no", "off"}


class InvalidDataHubConfigurationError(ValueError):
    """Raised when DataHub deployment configuration is invalid or unsafe."""


def parse_environment_boolean(
    value: str | None,
    *,
    variable_name: str,
    default: bool,
) -> bool:
    if value is None:
        return default

    normalized = value.strip().casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    accepted = ", ".join(sorted(_TRUE_VALUES | _FALSE_VALUES))
    raise InvalidDataHubConfigurationError(
        f"{variable_name} must be one of: {accepted} "
        f"(received {value!r})."
    )


def validate_datahub_gms_url(gms_url: str) -> str:
    normalized_url = gms_url.strip()
    if not normalized_url:
        raise InvalidDataHubConfigurationError(
            "DATAHUB_GMS_URL must not be empty when DataHub is used."
        )
    if any(character.isspace() for character in normalized_url):
        raise InvalidDataHubConfigurationError(
            "DATAHUB_GMS_URL must be a valid HTTP or HTTPS URL."
        )

    try:
        parsed_url = urlparse(normalized_url)
    except ValueError as exc:
        raise InvalidDataHubConfigurationError(
            "DATAHUB_GMS_URL must be a valid HTTP or HTTPS URL."
        ) from exc

    if (
        parsed_url.scheme.casefold() not in {"http", "https"}
        or not parsed_url.hostname
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise InvalidDataHubConfigurationError(
            "DATAHUB_GMS_URL must be a valid HTTP or HTTPS base URL."
        )
    if parsed_url.username or parsed_url.password:
        raise InvalidDataHubConfigurationError(
            "DATAHUB_GMS_URL must not contain embedded credentials."
        )

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
    streamlit_cloud_url = (
        hostname == "share.streamlit.io"
        or hostname == "streamlit.app"
        or hostname.endswith(".streamlit.app")
        or hostname.endswith(".streamlit.io")
    )
    if explicit_port == 8501 or codespaces_streamlit_url or streamlit_cloud_url:
        raise InvalidDataHubConfigurationError(
            "DATAHUB_GMS_URL appears to point to the Streamlit application "
            "rather than DataHub GMS. In a Codespace, set it to the internal "
            "endpoint http://localhost:8080; port 8501 is browser-facing only."
        )

    return normalized_url.rstrip("/")


class FallbackCaseProvider:
    def __init__(self, primary: CaseProvider, fallback: CaseProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self._fallback_active = False
        self._status = ProviderStatus(
            provider_name="datahub",
            datahub_connected=False,
            fallback_used=False,
            required_connection_failed=False,
            status_message="Automatic DataHub connection attempt has not run yet.",
        )

    @property
    def fallback_active(self) -> bool:
        return self._fallback_active

    @property
    def status(self) -> ProviderStatus:
        return self._status

    def list_cases(self) -> list[CaseAsset]:
        try:
            cases = self._primary.list_cases()
            self._fallback_active = False
            self._status = self._primary.status
            return cases
        except ProviderUnavailableError as exc:
            self._fallback_active = True
            cases = self._fallback.list_cases()
            self._status = ProviderStatus(
                provider_name="mock",
                datahub_connected=False,
                fallback_used=True,
                required_connection_failed=False,
                status_message=(
                    "DataHub is unavailable. Displaying the clearly labeled "
                    f"offline synthetic case catalog. ({exc})"
                ),
            )
            return cases


def create_provider(
    environ: Mapping[str, str] | None = None,
) -> CaseProvider:
    environment = os.environ if environ is None else environ
    mode = environment.get("DATAHUB_MODE", DEFAULT_DATAHUB_MODE).strip().casefold()
    if mode not in {"real", "mock", "auto"}:
        raise InvalidDataHubConfigurationError(
            "DATAHUB_MODE must be one of: real, mock, auto "
            f"(received {mode!r})."
        )

    datahub_required = parse_environment_boolean(
        environment.get("DATAHUB_REQUIRED"),
        variable_name="DATAHUB_REQUIRED",
        default=mode == "real",
    )

    if mode == "mock":
        if datahub_required:
            raise InvalidDataHubConfigurationError(
                "DATAHUB_REQUIRED=true cannot be combined with "
                "DATAHUB_MODE=mock."
            )
        return MockCaseProvider()

    gms_url = validate_datahub_gms_url(
        environment.get("DATAHUB_GMS_URL", DEFAULT_DATAHUB_GMS_URL)
    )
    if datahub_required:
        return required_datahub_provider(gms_url)
    if mode == "auto":
        return FallbackCaseProvider(
            primary=DataHubCaseProvider(gms_url),
            fallback=MockCaseProvider(),
        )
    return DataHubCaseProvider(gms_url)
