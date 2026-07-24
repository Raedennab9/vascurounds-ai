from __future__ import annotations

from typing import Any

from vascurounds.providers.datahub import DataHubCaseProvider


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


def _entity(
    code: str,
    title: str,
    description: str,
    *,
    synthetic: str = "true",
    educational: str = "true",
) -> dict[str, Any]:
    return {
        "urn": f"urn:li:dataset:(urn:li:dataPlatform:vascurounds,{code},PROD)",
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
