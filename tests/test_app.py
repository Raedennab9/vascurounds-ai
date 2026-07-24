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
