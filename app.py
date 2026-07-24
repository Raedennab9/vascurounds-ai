from __future__ import annotations

import streamlit as st

from vascurounds.models import (
    EDUCATIONAL_DISCLAIMER,
    EDUCATIONAL_STATUS_LABEL,
    SYNTHETIC_STATUS_LABEL,
    CaseAsset,
)
from vascurounds.providers.base import ProviderUnavailableError
from vascurounds.providers.factory import (
    InvalidDataHubConfigurationError,
    create_provider,
)


st.set_page_config(
    page_title="VascuRounds AI",
    page_icon="🩸",
    layout="centered",
)


def _render_safety_status(case: CaseAsset) -> None:
    left, right = st.columns(2)
    left.success(SYNTHETIC_STATUS_LABEL, icon="✅")
    right.success(EDUCATIONAL_STATUS_LABEL, icon="✅")


def _select_case(case: CaseAsset) -> None:
    st.session_state["selected_case_urn"] = case.urn
    st.rerun()


def _render_case_catalog(cases: list[CaseAsset]) -> None:
    st.header("Acute Limb Ischemia Case Conference")
    st.write(
        "Select a synthetic case to review its presentation and Rutherford "
        "classification."
    )

    for case in cases:
        with st.container(border=True):
            st.subheader(case.title)
            st.caption(case.rutherford_category)
            st.write(case.description)
            _render_safety_status(case)
            st.button(
                "View Case",
                key=f"view-{case.urn}",
                on_click=_select_case,
                args=(case,),
                use_container_width=True,
            )


def _render_case_overview(case: CaseAsset) -> None:
    if st.button("← Back to cases"):
        st.session_state.pop("selected_case_urn", None)
        st.rerun()

    st.caption("Case overview")
    st.title(case.title)
    st.subheader(case.rutherford_category)
    st.write(case.description)
    _render_safety_status(case)

    st.divider()
    if st.button(
        "Begin Case Conference",
        type="primary",
        use_container_width=True,
    ):
        st.info(
            "Staged questions and scoring will be introduced in the next milestone."
        )


def main() -> None:
    st.title("VascuRounds AI")
    st.info(EDUCATIONAL_DISCLAIMER, icon="ℹ️")

    try:
        provider = create_provider()
    except InvalidDataHubConfigurationError as exc:
        st.error("Invalid DataHub configuration.")
        st.write(str(exc))
        return

    try:
        cases = provider.list_cases()
    except ProviderUnavailableError as exc:
        st.error("VascuRounds AI could not retrieve cases from DataHub.")
        st.write(str(exc))
        st.caption(
            "Confirm that DATAHUB_GMS_URL is reachable, or set "
            "DATAHUB_MODE=mock for offline development."
        )
        return

    if provider.fallback_active:
        st.warning(
            "DataHub is unavailable. Displaying the clearly labeled offline "
            "synthetic case catalog."
        )

    if not cases:
        st.warning(
            "No DataHub case assets with confirmed synthetic-data and "
            "educational-use status were found."
        )
        return

    selected_urn = st.session_state.get("selected_case_urn")
    selected_case = next((case for case in cases if case.urn == selected_urn), None)

    if selected_case is None:
        st.session_state.pop("selected_case_urn", None)
        _render_case_catalog(cases)
    else:
        _render_case_overview(selected_case)

    st.divider()
    st.caption(EDUCATIONAL_DISCLAIMER)


if __name__ == "__main__":
    main()
