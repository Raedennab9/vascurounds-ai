from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from streamlit.testing.v1 import AppTest

from vascurounds.case_urns import ACUTE_LIMB_ISCHEMIA_URNS
from vascurounds.models import (
    EDUCATIONAL_DISCLAIMER,
    EDUCATIONAL_STATUS_LABEL,
    NO_DECISION_SUPPORT_LABEL,
    NO_PATIENT_DATA_LABEL,
    SYNTHETIC_STATUS_LABEL,
    CaseAsset,
)
from vascurounds.providers.base import ProviderStatus, ProviderUnavailableError
from vascurounds.providers.mock import MockCaseProvider


@dataclass
class StaticProvider:
    cases: list[CaseAsset]
    provider_status: ProviderStatus = field(
        default_factory=lambda: ProviderStatus(
            provider_name="datahub",
            datahub_connected=True,
            fallback_used=False,
            required_connection_failed=False,
            status_message=(
                "Synthetic educational cases loaded from DataHub metadata."
            ),
            endpoint="http://localhost:8080",
        )
    )
    error: ProviderUnavailableError | None = None

    @property
    def fallback_active(self) -> bool:
        return self.provider_status.fallback_used

    @property
    def status(self) -> ProviderStatus:
        return self.provider_status

    def list_cases(self) -> list[CaseAsset]:
        if self.error is not None:
            raise self.error
        return self.cases


def _mock_app(monkeypatch) -> AppTest:
    monkeypatch.setenv("DATAHUB_MODE", "mock")
    monkeypatch.setenv("DATAHUB_REQUIRED", "false")
    return AppTest.from_file("app.py").run()


def _begin_catalog_case(app: AppTest, index: int) -> AppTest:
    app.button[index].click().run()
    begin_button = next(
        button for button in app.button if button.label == "Begin Case Conference"
    )
    assert not begin_button.disabled
    begin_button.click().run()
    return app


def test_catalog_displays_all_required_safety_language(monkeypatch) -> None:
    app = _mock_app(monkeypatch)

    assert not app.exception
    assert EDUCATIONAL_DISCLAIMER in [message.value for message in app.info]
    status_messages = [message.value for message in app.success]
    for required_label in (
        SYNTHETIC_STATUS_LABEL,
        EDUCATIONAL_STATUS_LABEL,
        NO_PATIENT_DATA_LABEL,
        NO_DECISION_SUPPORT_LABEL,
    ):
        assert required_label in status_messages


def test_explicit_mock_mode_is_labeled_and_not_reported_as_connected(
    monkeypatch,
) -> None:
    app = _mock_app(monkeypatch)

    assert (
        "Offline demonstration active — bundled synthetic catalog "
        "(explicit mock mode). The live DataHub integration is available "
        "through the GitHub Codespace deployment."
    ) in [message.value for message in app.info]
    assert "DataHub connected — live integration active." not in [
        message.value for message in app.success
    ]
    assert not any(
        "loaded from DataHub metadata" in message.value
        for message in app.markdown
    )


@pytest.mark.parametrize(
    ("catalog_index", "category"),
    [
        (0, "Rutherford I"),
        (1, "Rutherford IIa"),
        (2, "Rutherford IIb"),
        (3, "Rutherford III"),
    ],
)
def test_each_registered_case_starts_the_shared_staged_conference(
    monkeypatch,
    catalog_index: int,
    category: str,
) -> None:
    app = _begin_catalog_case(_mock_app(monkeypatch), catalog_index)

    assert not app.exception
    assert "Stage 1: Initial recognition and focused assessment" in [
        header.value for header in app.header
    ]
    assert len(app.radio) == 1
    assert len(app.radio[0].options) == 4
    assert [option[:2] for option in app.radio[0].options] == [
        "A.",
        "B.",
        "C.",
        "D.",
    ]
    assert any(category in caption.value for caption in app.caption)
    conference_captions = " ".join(caption.value for caption in app.caption)
    assert NO_PATIENT_DATA_LABEL in conference_captions
    assert NO_DECISION_SUPPORT_LABEL in conference_captions
    assert EDUCATIONAL_DISCLAIMER in [message.value for message in app.info]
    assert "Stage 2: Rutherford classification" not in [
        header.value for header in app.header
    ]


def test_submitted_ui_answer_is_locked_and_correct_answer_is_shown(
    monkeypatch,
) -> None:
    app = _begin_catalog_case(_mock_app(monkeypatch), 2)

    app.radio[0].set_value(app.radio[0].options[0]).run()
    next(
        button for button in app.button if button.label == "Submit answer"
    ).click().run()

    assert not app.exception
    assert app.radio[0].disabled
    assert any(
        "Correct answer (" in message.value for message in app.markdown
    )
    assert any(
        button.label == "Continue to Next Stage" for button in app.button
    )
    assert EDUCATIONAL_DISCLAIMER in [message.value for message in app.info]


def test_unknown_urn_remains_overview_only(monkeypatch) -> None:
    unknown = CaseAsset(
        urn="urn:li:dataset:(urn:li:dataPlatform:file,unsupported,DEV)",
        title="Unsupported synthetic ALI case",
        rutherford_category="Rutherford I",
        description="Synthetic unsupported test fixture.",
        synthetic_data=True,
        educational_use=True,
    )
    monkeypatch.setattr(
        "vascurounds.providers.factory.create_provider",
        lambda: StaticProvider([unknown]),
    )

    app = AppTest.from_file("app.py").run()
    app.button[0].click().run()

    begin_button = next(
        button for button in app.button if button.label == "Begin Case Conference"
    )
    assert begin_button.disabled
    assert not app.radio
    assert any("overview-only" in message.value for message in app.info)


def test_matching_real_datahub_case_result_renders_a_conference(
    monkeypatch,
) -> None:
    real_case_result = MockCaseProvider().list_cases()[2]
    assert real_case_result.urn == ACUTE_LIMB_ISCHEMIA_URNS[2]
    monkeypatch.setattr(
        "vascurounds.providers.factory.create_provider",
        lambda: StaticProvider([real_case_result]),
    )

    app = AppTest.from_file("app.py").run()
    _begin_catalog_case(app, 0)

    assert not app.exception
    assert len(app.radio) == 1
    assert "Stage 1: Initial recognition and focused assessment" in [
        header.value for header in app.header
    ]
    assert "DataHub connected — live integration active." in [
        message.value for message in app.success
    ]
    assert any(
        "Synthetic educational cases loaded from DataHub metadata."
        in message.value
        for message in app.markdown
    )


def test_live_datahub_catalog_exposes_all_four_conferences(monkeypatch) -> None:
    monkeypatch.setattr(
        "vascurounds.providers.factory.create_provider",
        lambda: StaticProvider(MockCaseProvider().list_cases()),
    )

    app = AppTest.from_file("app.py").run()

    assert len(
        [button for button in app.button if button.label == "View Case"]
    ) == 4
    assert any(
        "4 eligible synthetic cases loaded from DataHub"
        in caption.value
        for caption in app.caption
    )


def test_datahub_unavailable_fallback_banner_and_conferences_remain_active(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "vascurounds.providers.factory.create_provider",
        lambda: StaticProvider(
            MockCaseProvider().list_cases(),
            provider_status=ProviderStatus(
                provider_name="mock",
                datahub_connected=False,
                fallback_used=True,
                required_connection_failed=False,
                status_message="Automatic offline fallback is active.",
            ),
        ),
    )

    app = AppTest.from_file("app.py").run()

    assert (
        "Offline demonstration active — bundled synthetic catalog "
        "(automatic fallback). The live DataHub integration is available "
        "through the GitHub Codespace deployment."
    ) in [warning.value for warning in app.warning]
    assert "DataHub connected — live integration active." not in [
        message.value for message in app.success
    ]
    assert not any(
        "loaded from DataHub metadata" in message.value
        for message in app.markdown
    )
    assert len(
        [button for button in app.button if button.label == "View Case"]
    ) == 4
    _begin_catalog_case(app, 0)
    assert len(app.radio) == 1


def test_required_datahub_failure_blocks_catalog_and_conference(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "vascurounds.providers.factory.create_provider",
        lambda: StaticProvider(
            MockCaseProvider().list_cases(),
            provider_status=ProviderStatus(
                provider_name="datahub",
                datahub_connected=False,
                fallback_used=False,
                required_connection_failed=True,
                status_message="DataHub connection was refused.",
                endpoint="http://localhost:8080",
            ),
            error=ProviderUnavailableError("DataHub connection was refused."),
        ),
    )

    app = AppTest.from_file("app.py").run()

    assert "DataHub connection required but unavailable." in [
        message.value for message in app.error
    ]
    assert not [
        button for button in app.button if button.label == "View Case"
    ]
    assert not app.radio
    assert "DataHub connected — live integration active." not in [
        message.value for message in app.success
    ]
    assert EDUCATIONAL_DISCLAIMER in [message.value for message in app.info]


def test_switching_cases_starts_a_fresh_isolated_attempt(monkeypatch) -> None:
    app = _begin_catalog_case(_mock_app(monkeypatch), 0)
    first_case_options = tuple(app.radio[0].options)
    app.radio[0].set_value(app.radio[0].options[0]).run()
    next(
        button for button in app.button if button.label == "Submit answer"
    ).click().run()
    assert app.radio[0].disabled

    next(
        button for button in app.button if button.label == "Change Case"
    ).click().run()
    assert len([button for button in app.button if button.label == "View Case"]) == 4

    _begin_catalog_case(app, 1)

    assert len(app.radio) == 1
    assert not app.radio[0].disabled
    assert not any(
        "Correct answer (" in message.value for message in app.markdown
    )
    assert tuple(app.radio[0].options) != first_case_options
    assert any("Rutherford IIa" in caption.value for caption in app.caption)


def test_performance_report_contains_case_results_and_ui_restart(
    monkeypatch,
) -> None:
    app = _begin_catalog_case(_mock_app(monkeypatch), 3)

    for stage_number in range(1, 6):
        app.radio[0].set_value(app.radio[0].options[0]).run()
        next(
            button for button in app.button if button.label == "Submit answer"
        ).click().run()
        progression_label = (
            "View Performance Report"
            if stage_number == 5
            else "Continue to Next Stage"
        )
        next(
            button
            for button in app.button
            if button.label == progression_label
        ).click().run()

    assert "Performance report" in [title.value for title in app.title]
    assert any(
        "Selected case:" in message.value
        and "Rutherford III" in message.value
        for message in app.markdown
    )
    assert "Rutherford III" in [caption.value for caption in app.caption]
    metrics = {metric.label: metric.value for metric in app.metric}
    total_score = int(metrics["Total score"].split()[0])
    correct_answers = int(metrics["Correct answers"].split()[0])
    assert total_score == correct_answers * 20
    assert 0 <= total_score <= 100
    assert any(
        heading.value == "Educational strengths" for heading in app.subheader
    )
    assert any(
        heading.value == "Topics requiring review" for heading in app.subheader
    )
    assert EDUCATIONAL_DISCLAIMER in [message.value for message in app.info]

    report_orders = {
        stage_id: tuple(order)
        for stage_id, order in app.session_state[
            "conference_attempt"
        ].option_orders.items()
    }
    next(
        button for button in app.button if button.label == "Restart Case"
    ).click().run()

    assert "Stage 1: Initial recognition and focused assessment" in [
        header.value for header in app.header
    ]
    assert len(app.radio) == 1
    assert not app.radio[0].disabled
    restarted_attempt = app.session_state["conference_attempt"]
    assert restarted_attempt.score == 0
    assert restarted_attempt.answers == {}
    assert all(
        restarted_attempt.option_orders[stage_id] != previous_order
        for stage_id, previous_order in report_orders.items()
    )


def test_invalid_streamlit_url_is_reported_as_datahub_configuration_error(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATAHUB_MODE", "real")
    monkeypatch.setenv("DATAHUB_REQUIRED", "true")
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8501")

    app = AppTest.from_file("app.py").run()

    assert not app.exception
    assert "Invalid DataHub configuration." in [
        message.value for message in app.error
    ]
    assert any(
        "http://localhost:8080" in message.value for message in app.markdown
    )
