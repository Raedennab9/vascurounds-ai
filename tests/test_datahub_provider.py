from __future__ import annotations

from typing import Any

import pytest
import requests

from vascurounds.case_urns import ACUTE_LIMB_ISCHEMIA_URNS
from vascurounds.providers.base import ProviderUnavailableError
from vascurounds.providers.datahub import (
    DataHubCaseProvider,
    required_datahub_provider,
)
from vascurounds.providers.mock import MockCaseProvider


class StubResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._body


class StubSession:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body
        self.url = ""
        self.payload: dict[str, Any] = {}

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> StubResponse:
        self.url = url
        self.payload = json
        assert timeout == 5.0
        return StubResponse(self._body)


class FailingSession:
    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> StubResponse:
        raise requests.ConnectionError("connection refused")


def _entity(
    code: str,
    title: str,
    description: str,
    *,
    synthetic: str = "true",
    educational: str = "true",
    urn: str | None = None,
) -> dict[str, Any]:
    return {
        "urn": urn
        or f"urn:li:dataset:(urn:li:dataPlatform:vascurounds,{code},PROD)",
        "type": "DATASET",
        "name": code,
        "properties": {
            "name": title,
            "description": description,
            "customProperties": [
                {"key": "rutherford_category", "value": code},
                {"key": "synthetic_data_status", "value": synthetic},
                {"key": "educational_use_status", "value": educational},
            ],
        },
        "tags": {"tags": []},
    }


def _seeded_entity(
    code: str,
    title: str,
    *,
    include_data_type: bool = True,
) -> dict[str, Any]:
    custom_properties = [
        {"key": "rutherford_class", "value": code},
        {
            "key": "intended_use",
            "value": "Professional education and simulation",
        },
        {"key": "contains_patient_data", "value": "No"},
        {"key": "decision_support", "value": "No"},
    ]
    if include_data_type:
        custom_properties.insert(
            1,
            {"key": "data_type", "value": "Synthetic educational case"},
        )

    return {
        "urn": f"urn:li:dataset:(urn:li:dataPlatform:vascurounds,{code},PROD)",
        "type": "DATASET",
        "name": code,
        "properties": {
            "name": title,
            "description": f"Synthetic acute limb ischemia case: {title}.",
            "customProperties": custom_properties,
        },
        "tags": {"tags": []},
    }


def test_retrieves_and_sorts_eligible_datahub_cases() -> None:
    body = {
        "data": {
            "searchAcrossEntities": {
                "searchResults": [
                    {"entity": _entity("III", "Irreversible", "Case three")},
                    {"entity": _entity("I", "Viable", "Case one")},
                    {
                        "entity": _entity(
                            "IIb",
                            "Immediately Threatened",
                            "Case two-b",
                        )
                    },
                    {
                        "entity": _entity(
                            "IIa",
                            "Marginally Threatened",
                            "Case two-a",
                        )
                    },
                    {
                        "entity": _entity(
                            "unsafe",
                            "Rutherford I — Unsafe",
                            "Must not be displayed",
                            synthetic="false",
                        )
                    },
                ]
            }
        }
    }
    session = StubSession(body)
    provider = DataHubCaseProvider("http://localhost:8080/", session=session)  # type: ignore[arg-type]

    cases = provider.list_cases()

    assert session.url == "http://localhost:8080/api/graphql"
    assert session.payload["variables"]["input"]["types"] == ["DATASET"]
    assert [case.rutherford_category for case in cases] == [
        "Rutherford I",
        "Rutherford IIa",
        "Rutherford IIb",
        "Rutherford III",
    ]
    assert all(case.synthetic_data and case.educational_use for case in cases)
    assert all(case.description for case in cases)
    assert provider.status.provider_name == "datahub"
    assert provider.status.datahub_connected is True
    assert provider.status.fallback_used is False
    assert provider.status.required_connection_failed is False


def test_accepts_exact_seed_metadata_and_rejects_missing_synthetic_evidence() -> None:
    body = {
        "data": {
            "searchAcrossEntities": {
                "searchResults": [
                    {
                        "entity": _seeded_entity(
                            "IIb",
                            "Rutherford IIb — Immediately Threatened",
                        )
                    },
                    {
                        "entity": _seeded_entity(
                            "I",
                            "Rutherford I — Missing Synthetic Evidence",
                            include_data_type=False,
                        )
                    },
                ]
            }
        }
    }
    provider = DataHubCaseProvider(
        "http://localhost:8080",
        session=StubSession(body),  # type: ignore[arg-type]
    )

    cases = provider.list_cases()

    assert len(cases) == 1
    assert cases[0].title == "Rutherford IIb — Immediately Threatened"
    assert cases[0].rutherford_category == "Rutherford IIb"
    assert cases[0].synthetic_data is True
    assert cases[0].educational_use is True


def test_real_and_mock_providers_preserve_the_same_canonical_case_urns() -> None:
    codes_and_titles = (
        ("I", "Rutherford I — Viable"),
        ("IIa", "Rutherford IIa — Marginally Threatened"),
        ("IIb", "Rutherford IIb — Immediately Threatened"),
        ("III", "Rutherford III — Irreversible"),
    )
    body = {
        "data": {
            "searchAcrossEntities": {
                "searchResults": [
                    {
                        "entity": _entity(
                            code,
                            title,
                            "Synthetic acute limb ischemia conference.",
                            urn=urn,
                        )
                    }
                    for (code, title), urn in zip(
                        codes_and_titles,
                        ACUTE_LIMB_ISCHEMIA_URNS,
                        strict=True,
                    )
                ]
            }
        }
    }
    real_provider = DataHubCaseProvider(
        "http://localhost:8080",
        session=StubSession(body),  # type: ignore[arg-type]
    )

    real_urns = tuple(case.urn for case in real_provider.list_cases())
    mock_urns = tuple(case.urn for case in MockCaseProvider().list_cases())

    assert real_urns == ACUTE_LIMB_ISCHEMIA_URNS
    assert mock_urns == ACUTE_LIMB_ISCHEMIA_URNS


def test_required_provider_blocks_when_a_canonical_dataset_is_missing() -> None:
    body = {
        "data": {
            "searchAcrossEntities": {
                "searchResults": [
                    {
                        "entity": _entity(
                            code,
                            title,
                            "Synthetic acute limb ischemia conference.",
                            urn=urn,
                        )
                    }
                    for code, title, urn in zip(
                        ("I", "IIa", "IIb"),
                        ("Viable", "Marginal", "Immediate"),
                        ACUTE_LIMB_ISCHEMIA_URNS[:3],
                        strict=True,
                    )
                ]
            }
        }
    }
    provider = required_datahub_provider(
        "http://localhost:8080",
        session=StubSession(body),  # type: ignore[arg-type]
    )

    with pytest.raises(
        ProviderUnavailableError,
        match="missing 1 of 4 required",
    ):
        provider.list_cases()

    assert provider.status.provider_name == "datahub"
    assert provider.status.datahub_connected is False
    assert provider.status.fallback_used is False
    assert provider.status.required_connection_failed is True


def test_required_provider_connection_error_records_blocking_state() -> None:
    provider = required_datahub_provider(
        "http://localhost:8080",
        session=FailingSession(),  # type: ignore[arg-type]
    )

    with pytest.raises(ProviderUnavailableError, match="connection refused"):
        provider.list_cases()

    assert provider.status.datahub_connected is False
    assert provider.status.fallback_used is False
    assert provider.status.required_connection_failed is True
    assert provider.status.endpoint == "http://localhost:8080"
