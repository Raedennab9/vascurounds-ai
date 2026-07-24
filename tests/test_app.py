from __future__ import annotations

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
