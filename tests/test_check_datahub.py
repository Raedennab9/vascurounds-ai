from __future__ import annotations

from typing import Any

import pytest
import requests

from scripts.check_datahub import REQUEST_TIMEOUT, run_health_check
from vascurounds.case_urns import ACUTE_LIMB_ISCHEMIA_URNS


class StubResponse:
    def __init__(
        self,
        body: Any = None,
        *,
        http_error: requests.HTTPError | None = None,
        json_error: ValueError | None = None,
    ) -> None:
        self._body = body
        self._http_error = http_error
        self._json_error = json_error

    def raise_for_status(self) -> None:
        if self._http_error is not None:
            raise self._http_error

    def json(self) -> Any:
        if self._json_error is not None:
            raise self._json_error
        return self._body


class StubSession:
    def __init__(
        self,
        *,
        config_response: StubResponse | None = None,
        graphql_response: StubResponse | None = None,
        dataset_response: StubResponse | None = None,
        get_error: requests.RequestException | None = None,
        post_error: requests.RequestException | None = None,
    ) -> None:
        self.config_response = config_response or StubResponse({})
        self.graphql_response = graphql_response or StubResponse(
            {"data": {"__typename": "Query"}}
        )
        self.dataset_response = dataset_response or StubResponse(
            _dataset_search_body(ACUTE_LIMB_ISCHEMIA_URNS)
        )
        self.get_error = get_error
        self.post_error = post_error
        self.get_calls: list[tuple[str, tuple[float, float]]] = []
        self.post_calls: list[
            tuple[str, dict[str, Any], float | tuple[float, float]]
        ] = []

    def get(
        self,
        url: str,
        *,
        timeout: tuple[float, float],
    ) -> StubResponse:
        self.get_calls.append((url, timeout))
        if self.get_error is not None:
            raise self.get_error
        return self.config_response

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float | tuple[float, float],
    ) -> StubResponse:
        self.post_calls.append((url, json, timeout))
        if self.post_error is not None:
            raise self.post_error
        if len(self.post_calls) == 1:
            return self.graphql_response
        return self.dataset_response


def _dataset_search_body(urns: tuple[str, ...]) -> dict[str, Any]:
    codes = ("I", "IIa", "IIb", "III")
    titles = (
        "Rutherford I — Viable",
        "Rutherford IIa — Marginally Threatened",
        "Rutherford IIb — Immediately Threatened",
        "Rutherford III — Irreversible",
    )
    return {
        "data": {
            "searchAcrossEntities": {
                "searchResults": [
                    {
                        "entity": {
                            "urn": urn,
                            "type": "DATASET",
                            "properties": {
                                "name": title,
                                "description": "Synthetic educational ALI case.",
                                "customProperties": [
                                    {
                                        "key": "rutherford_class",
                                        "value": code,
                                    },
                                    {
                                        "key": "data_type",
                                        "value": "Synthetic educational case",
                                    },
                                    {
                                        "key": "intended_use",
                                        "value": (
                                            "Professional education and simulation"
                                        ),
                                    },
                                    {
                                        "key": "contains_patient_data",
                                        "value": "No",
                                    },
                                    {
                                        "key": "decision_support",
                                        "value": "No",
                                    },
                                ],
                            },
                            "tags": {"tags": []},
                        }
                    }
                    for urn, code, title in zip(
                        urns,
                        codes[: len(urns)],
                        titles[: len(urns)],
                        strict=True,
                    )
                ]
            }
        }
    }


def _run(session: StubSession) -> tuple[int, list[str]]:
    output: list[str] = []
    exit_code = run_health_check(
        {"DATAHUB_GMS_URL": "http://localhost:8080"},
        session=session,
        output=output.append,
    )
    return exit_code, output


def test_complete_four_dataset_health_check_succeeds() -> None:
    session = StubSession()

    exit_code, output = _run(session)

    assert exit_code == 0
    assert output == [
        "DataHub GMS health check passed.",
        "GraphQL endpoint responded successfully.",
        "Found 4 of 4 required VascuRounds datasets.",
        "Competition DataHub integration is ready.",
    ]
    assert session.get_calls == [
        ("http://localhost:8080/config", REQUEST_TIMEOUT)
    ]
    assert len(session.post_calls) == 2
    assert session.post_calls[0][0] == "http://localhost:8080/api/graphql"
    assert session.post_calls[0][1] == {"query": "query { __typename }"}
    assert all(call[2] == REQUEST_TIMEOUT for call in session.post_calls)


@pytest.mark.parametrize(
    "connection_error",
    [
        requests.ConnectionError("connection refused"),
        requests.Timeout("request timed out"),
    ],
)
def test_config_connection_failure_or_timeout_is_nonzero(
    connection_error: requests.RequestException,
) -> None:
    exit_code, output = _run(StubSession(get_error=connection_error))

    assert exit_code == 1
    assert "DataHub /config health check failed" in output[-1]


def test_config_non_success_http_status_is_nonzero() -> None:
    session = StubSession(
        config_response=StubResponse(
            http_error=requests.HTTPError("503 Service Unavailable")
        )
    )

    exit_code, output = _run(session)

    assert exit_code == 1
    assert "503 Service Unavailable" in output[-1]


def test_graphql_malformed_json_is_nonzero_after_config_success() -> None:
    session = StubSession(
        graphql_response=StubResponse(
            json_error=ValueError("invalid JSON")
        )
    )

    exit_code, output = _run(session)

    assert exit_code == 1
    assert output[0] == "DataHub GMS health check passed."
    assert "DataHub GraphQL health check failed" in output[-1]


def test_graphql_errors_are_nonzero() -> None:
    session = StubSession(
        graphql_response=StubResponse(
            {"errors": [{"message": "GraphQL unavailable"}]}
        )
    )

    exit_code, output = _run(session)

    assert exit_code == 1
    assert "GraphQL returned errors" in output[-1]


def test_graphql_without_valid_data_is_nonzero() -> None:
    session = StubSession(
        graphql_response=StubResponse({"data": {}})
    )

    exit_code, output = _run(session)

    assert exit_code == 1
    assert "valid GraphQL data was absent" in output[-1]


def test_missing_required_dataset_is_nonzero() -> None:
    session = StubSession(
        dataset_response=StubResponse(
            _dataset_search_body(ACUTE_LIMB_ISCHEMIA_URNS[:3])
        )
    )

    exit_code, output = _run(session)

    assert exit_code == 1
    assert "GraphQL endpoint responded successfully." in output
    assert "Found 3 of 4 required VascuRounds datasets." in output
    assert "1 required dataset(s) are missing" in output[-1]


def test_malformed_dataset_search_response_is_nonzero_with_clear_diagnostic() -> None:
    session = StubSession(
        dataset_response=StubResponse(
            {
                "data": {
                    "searchAcrossEntities": {
                        "searchResults": None,
                    }
                }
            }
        )
    )

    exit_code, output = _run(session)

    assert exit_code == 1
    assert "VascuRounds dataset query failed" in output[-1]
    assert "searchResults was not a list" in output[-1]


def test_port_8501_configuration_is_rejected_without_http_requests() -> None:
    session = StubSession()
    output: list[str] = []

    exit_code = run_health_check(
        {"DATAHUB_GMS_URL": "https://codespace-8501.app.github.dev"},
        session=session,
        output=output.append,
    )

    assert exit_code == 1
    assert "Invalid DataHub configuration" in output[0]
    assert session.get_calls == []
    assert session.post_calls == []
