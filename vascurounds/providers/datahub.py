from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import requests

from vascurounds.case_urns import ACUTE_LIMB_ISCHEMIA_URNS
from vascurounds.models import (
    CaseAsset,
    normalize_rutherford_category,
    sort_cases_clinically,
)
from vascurounds.providers.base import ProviderStatus, ProviderUnavailableError


SEARCH_CASES_QUERY = """
query SearchVascuRoundsCases($input: SearchAcrossEntitiesInput!) {
  searchAcrossEntities(input: $input) {
    searchResults {
      entity {
        urn
        type
        ... on Dataset {
          name
          properties {
            name
            description
            customProperties {
              key
              value
            }
          }
          tags {
            tags {
              tag {
                name
              }
            }
          }
        }
      }
    }
  }
}
"""

_RUTHERFORD_KEYS = {
    "rutherford",
    "rutherfordcategory",
    "rutherfordclass",
    "clinicalcategory",
    "classification",
}
_SYNTHETIC_KEYS = {
    "synthetic",
    "syntheticdata",
    "syntheticdatastatus",
    "datatype",
    "issynthetic",
    "datasource",
    "datastatus",
}
_EDUCATIONAL_KEYS = {
    "educational",
    "educationalonly",
    "educationaluse",
    "educationalusestatus",
    "iseducational",
    "intendeduse",
}
_TRUE_VALUES = {"1", "true", "yes", "confirmed", "synthetic", "educational"}
RequestTimeout = float | tuple[float, float]


class DataHubCaseProvider:
    def __init__(
        self,
        gms_url: str,
        *,
        timeout_seconds: RequestTimeout = 5.0,
        session: requests.Session | None = None,
        required_connection: bool = False,
        required_urns: tuple[str, ...] = (),
    ) -> None:
        self._gms_url = gms_url.rstrip("/")
        self._graphql_url = f"{self._gms_url}/api/graphql"
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._required_connection = required_connection
        self._required_urns = required_urns
        self._status = ProviderStatus(
            provider_name="datahub",
            datahub_connected=False,
            fallback_used=False,
            required_connection_failed=False,
            status_message="Live DataHub case retrieval has not run yet.",
            endpoint=self._gms_url,
        )

    @property
    def fallback_active(self) -> bool:
        return False

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @property
    def required_urns(self) -> tuple[str, ...]:
        return self._required_urns

    def _record_failure(self, message: str) -> None:
        self._status = ProviderStatus(
            provider_name="datahub",
            datahub_connected=False,
            fallback_used=False,
            required_connection_failed=self._required_connection,
            status_message=message,
            endpoint=self._gms_url,
        )

    def list_cases(self) -> list[CaseAsset]:
        payload = {
            "query": SEARCH_CASES_QUERY,
            "variables": {
                "input": {
                    "types": ["DATASET"],
                    "query": "*",
                    "start": 0,
                    "count": 100,
                }
            },
        }

        try:
            response = self._session.post(
                self._graphql_url,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            message = f"Unable to query DataHub GMS: {exc}"
            self._record_failure(message)
            raise ProviderUnavailableError(message) from exc

        if not isinstance(body, Mapping):
            message = "DataHub returned a non-object GraphQL response."
            self._record_failure(message)
            raise ProviderUnavailableError(message)

        errors = body.get("errors")
        if errors:
            if isinstance(errors, list):
                message = "; ".join(
                    str(error.get("message", error))
                    if isinstance(error, Mapping)
                    else str(error)
                    for error in errors
                )
            else:
                message = str(errors)
            failure_message = f"DataHub GraphQL query failed: {message}"
            self._record_failure(failure_message)
            raise ProviderUnavailableError(failure_message)

        try:
            results = body["data"]["searchAcrossEntities"]["searchResults"]
        except (KeyError, TypeError) as exc:
            message = "DataHub returned an unexpected GraphQL response."
            self._record_failure(message)
            raise ProviderUnavailableError(message) from exc

        if not isinstance(results, list):
            message = (
                "DataHub returned an unexpected GraphQL response: "
                "searchResults was not a list."
            )
            self._record_failure(message)
            raise ProviderUnavailableError(message)

        cases: list[CaseAsset] = []
        for result in results:
            if not isinstance(result, Mapping):
                message = (
                    "DataHub returned an unexpected GraphQL response: "
                    "a search result was not an object."
                )
                self._record_failure(message)
                raise ProviderUnavailableError(message)
            entity = result.get("entity") or {}
            if not isinstance(entity, Mapping):
                message = (
                    "DataHub returned an unexpected GraphQL response: "
                    "a dataset entity was not an object."
                )
                self._record_failure(message)
                raise ProviderUnavailableError(message)
            case = _case_from_entity(entity)
            if case is not None:
                cases.append(case)

        sorted_cases = sort_cases_clinically(cases)
        available_urns = {case.urn for case in sorted_cases}
        missing_urns = [
            urn for urn in self._required_urns if urn not in available_urns
        ]
        if missing_urns:
            message = (
                "DataHub is reachable but is missing "
                f"{len(missing_urns)} of {len(self._required_urns)} required "
                "VascuRounds datasets."
            )
            self._record_failure(message)
            raise ProviderUnavailableError(message)

        self._status = ProviderStatus(
            provider_name="datahub",
            datahub_connected=True,
            fallback_used=False,
            required_connection_failed=False,
            status_message=(
                "Synthetic educational cases loaded from DataHub metadata."
            ),
            endpoint=self._gms_url,
        )
        return sorted_cases


def required_datahub_provider(
    gms_url: str,
    *,
    timeout_seconds: RequestTimeout = 5.0,
    session: requests.Session | None = None,
) -> DataHubCaseProvider:
    """Build a provider that requires the complete competition case catalog."""

    return DataHubCaseProvider(
        gms_url,
        timeout_seconds=timeout_seconds,
        session=session,
        required_connection=True,
        required_urns=ACUTE_LIMB_ISCHEMIA_URNS,
    )


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _custom_properties(entity: Mapping[str, Any]) -> dict[str, str]:
    properties = entity.get("properties") or {}
    raw_custom_properties = properties.get("customProperties") or []
    return {
        _normalize_key(str(item.get("key", ""))): str(item.get("value", "")).strip()
        for item in raw_custom_properties
        if item.get("key")
    }


def _tag_names(entity: Mapping[str, Any]) -> set[str]:
    tags = (entity.get("tags") or {}).get("tags") or []
    return {
        _normalize_key(str((item.get("tag") or {}).get("name", "")))
        for item in tags
    }


def _first_property(metadata: Mapping[str, str], keys: set[str]) -> str:
    for key in keys:
        value = metadata.get(key)
        if value:
            return value
    return ""


def _status_is_confirmed(
    metadata: Mapping[str, str],
    keys: set[str],
    tags: set[str],
    tag_markers: set[str],
) -> bool:
    value = _first_property(metadata, keys).casefold()
    if value in _TRUE_VALUES:
        return True
    if any(marker in value for marker in tag_markers):
        return True
    return any(marker in tag for tag in tags for marker in tag_markers)


def _infer_category(*values: str) -> str | None:
    for value in values:
        category = normalize_rutherford_category(value)
        if category is not None:
            return category
    return None


def _case_from_entity(entity: Mapping[str, Any]) -> CaseAsset | None:
    if entity.get("type") not in (None, "DATASET"):
        return None

    properties = entity.get("properties") or {}
    metadata = _custom_properties(entity)
    tags = _tag_names(entity)

    title = str(properties.get("name") or entity.get("name") or "").strip()
    description = str(properties.get("description") or "").strip()
    urn = str(entity.get("urn") or "").strip()
    category = _infer_category(
        _first_property(metadata, _RUTHERFORD_KEYS),
        title,
        description,
        urn,
    )

    synthetic_data = _status_is_confirmed(
        metadata,
        _SYNTHETIC_KEYS,
        tags,
        {"synthetic", "syntheticdata", "syntheticonly"},
    )
    educational_use = _status_is_confirmed(
        metadata,
        _EDUCATIONAL_KEYS,
        tags,
        {"educational", "education", "simulation"},
    )

    if not urn or not title or category is None:
        return None
    if not synthetic_data or not educational_use:
        return None

    return CaseAsset(
        urn=urn,
        title=title,
        rutherford_category=category,
        description=description or "No description was supplied by DataHub.",
        synthetic_data=True,
        educational_use=True,
    )
