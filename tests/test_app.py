from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from vascurounds.models import (
    EDUCATIONAL_DISCLAIMER,
    EDUCATIONAL_STATUS_LABEL,
    SYNTHETIC_STATUS_LABEL,
)


def test_catalog_displays_required_safety_language(monkeypatch) -> None:
    monkeypatch.setenv("DATAHUB_MODE", "mock")

    app = AppTest.from_file("app.py").run()

    assert not app.exception
    assert EDUCATIONAL_DISCLAIMER in [message.value for message in app.info]
    status_messages = [message.value for message in app.success]
    assert SYNTHETIC_STATUS_LABEL in status_messages
    assert EDUCATIONAL_STATUS_LABEL in status_messages


def test_rutherford_iia_case_starts_the_staged_conference(monkeypatch) -> None:
    monkeypatch.setenv("DATAHUB_MODE", "mock")

    app = AppTest.from_file("app.py").run()
    app.button[1].click().run()

    begin_button = next(
        button for button in app.button if button.label == "Begin Case Conference"
    )
    assert not begin_button.disabled

    begin_button.click().run()

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
    assert EDUCATIONAL_DISCLAIMER in [message.value for message in app.info]
    assert "Stage 2: Rutherford classification" not in [
        header.value for header in app.header
    ]


def test_submitted_ui_answer_is_locked_and_correct_answer_is_shown(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATAHUB_MODE", "mock")

    app = AppTest.from_file("app.py").run()
    app.button[1].click().run()
    next(
        button for button in app.button if button.label == "Begin Case Conference"
    ).click().run()

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


@pytest.mark.parametrize("catalog_button_index", [0, 2, 3])
def test_other_rutherford_cases_remain_overview_only(
    monkeypatch,
    catalog_button_index: int,
) -> None:
    monkeypatch.setenv("DATAHUB_MODE", "mock")

    app = AppTest.from_file("app.py").run()
    app.button[catalog_button_index].click().run()

    begin_button = next(
        button for button in app.button if button.label == "Begin Case Conference"
    )
    assert begin_button.disabled
    assert not app.radio
    assert any(
        "overview-only" in message.value for message in app.info
    )


def test_performance_report_and_ui_restart(monkeypatch) -> None:
    monkeypatch.setenv("DATAHUB_MODE", "mock")

    app = AppTest.from_file("app.py").run()
    app.button[1].click().run()
    next(
        button for button in app.button if button.label == "Begin Case Conference"
    ).click().run()

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

    next(
        button for button in app.button if button.label == "Restart Case"
    ).click().run()

    assert "Stage 1: Initial recognition and focused assessment" in [
        header.value for header in app.header
    ]
    assert len(app.radio) == 1
    assert not app.radio[0].disabled


def test_invalid_streamlit_url_is_reported_as_datahub_configuration_error(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATAHUB_MODE", "real")
    monkeypatch.setenv("DATAHUB_GMS_URL", "http://localhost:8501")

    app = AppTest.from_file("app.py").run()

    assert not app.exception
    assert "Invalid DataHub configuration." in [
        message.value for message in app.error
    ]
    assert any(
        "http://localhost:8080" in message.value for message in app.markdown
    )
