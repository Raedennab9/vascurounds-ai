#!/usr/bin/env python3
"""Fail-fast health check for the competition DataHub integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from pathlib import Path
import sys
from typing import Any, Protocol

import requests


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from vascurounds.case_urns import ACUTE_LIMB_ISCHEMIA_URNS
from vascurounds.providers.base import ProviderUnavailableError
from vascurounds.providers.datahub import DataHubCaseProvider
from vascurounds.providers.factory import (
    DEFAULT_DATAHUB_GMS_URL,
    InvalidDataHubConfigurationError,
    validate_datahub_gms_url,
)


REQUEST_TIMEOUT = (3.05, 10.0)
MINIMAL_GRAPHQL_QUERY = "query { __typename }"


class HttpSession(Protocol):
    def get(self, url: str, *, timeout: tuple[float, float]) -> Any:
        """Issue an HTTP GET request."""

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float | tuple[float, float],
    ) -> Any:
        """Issue an HTTP POST request."""


def _request_failed(
    *,
    action: str,
    error: Exception,
    output: Callable[[str], None],
) -> int:
    output(f"{action} failed: {error}")
    return 1


def run_health_check(
    environ: Mapping[str, str] | None = None,
    *,
    session: HttpSession | None = None,
    output: Callable[[str], None] = print,
) -> int:
    """Return zero only when GMS, GraphQL, and all required datasets are ready."""

    environment = os.environ if environ is None else environ
    try:
        gms_url = validate_datahub_gms_url(
            environment.get("DATAHUB_GMS_URL", DEFAULT_DATAHUB_GMS_URL)
        )
    except InvalidDataHubConfigurationError as exc:
        output(f"Invalid DataHub configuration: {exc}")
        return 1

    http = requests.Session() if session is None else session

    try:
        config_response = http.get(
            f"{gms_url}/config",
            timeout=REQUEST_TIMEOUT,
        )
        config_response.raise_for_status()
    except (requests.RequestException, ValueError) as exc:
        return _request_failed(
            action="DataHub /config health check",
            error=exc,
            output=output,
        )
    output("DataHub GMS health check passed.")

    try:
        graphql_response = http.post(
            f"{gms_url}/api/graphql",
            json={"query": MINIMAL_GRAPHQL_QUERY},
            timeout=REQUEST_TIMEOUT,
        )
        graphql_response.raise_for_status()
        graphql_body = graphql_response.json()
    except (requests.RequestException, ValueError) as exc:
        return _request_failed(
            action="DataHub GraphQL health check",
            error=exc,
            output=output,
        )

    if not isinstance(graphql_body, Mapping):
        output("DataHub GraphQL health check failed: response was not a JSON object.")
        return 1
    if graphql_body.get("errors"):
        output("DataHub GraphQL health check failed: GraphQL returned errors.")
        return 1
    graphql_data = graphql_body.get("data")
    if (
        not isinstance(graphql_data, Mapping)
        or not isinstance(graphql_data.get("__typename"), str)
        or not graphql_data["__typename"]
    ):
        output("DataHub GraphQL health check failed: valid GraphQL data was absent.")
        return 1
    output("GraphQL endpoint responded successfully.")

    provider = DataHubCaseProvider(
        gms_url,
        timeout_seconds=REQUEST_TIMEOUT,
        session=http,  # type: ignore[arg-type]
    )
    try:
        cases = provider.list_cases()
    except ProviderUnavailableError as exc:
        return _request_failed(
            action="VascuRounds dataset query",
            error=exc,
            output=output,
        )

    available_urns = {case.urn for case in cases}
    found_count = sum(
        urn in available_urns for urn in ACUTE_LIMB_ISCHEMIA_URNS
    )
    output(
        f"Found {found_count} of {len(ACUTE_LIMB_ISCHEMIA_URNS)} "
        "required VascuRounds datasets."
    )
    if found_count != len(ACUTE_LIMB_ISCHEMIA_URNS):
        missing_count = len(ACUTE_LIMB_ISCHEMIA_URNS) - found_count
        output(
            f"Competition DataHub integration is not ready: "
            f"{missing_count} required dataset(s) are missing."
        )
        return 1

    output("Competition DataHub integration is ready.")
    return 0


def main() -> int:
    return run_health_check()


if __name__ == "__main__":
    raise SystemExit(main())
