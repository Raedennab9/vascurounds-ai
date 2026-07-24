from __future__ import annotations

import streamlit as st

from vascurounds.conference.content import (
    ContentValidationError,
    RUTHERFORD_IIA_DATAHUB_URN,
    load_rutherford_iia_conference,
)
from vascurounds.conference.engine import (
    advance_stage,
    current_stage,
    presented_choices,
    restart_attempt,
    start_attempt,
    submit_answer,
)
from vascurounds.conference.models import (
    AnswerRecord,
    AttemptState,
    ConferenceDefinition,
)
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
    st.session_state.pop("conference_attempt", None)
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


def _render_case_overview(
    case: CaseAsset,
    definition: ConferenceDefinition | None,
) -> None:
    if st.button("← Back to cases"):
        st.session_state.pop("selected_case_urn", None)
        st.session_state.pop("conference_attempt", None)
        st.rerun()

    st.caption("Case overview")
    st.title(case.title)
    st.subheader(case.rutherford_category)
    st.write(case.description)
    _render_safety_status(case)

    st.divider()
    begin_clicked = st.button(
        "Begin Case Conference",
        type="primary",
        use_container_width=True,
        disabled=definition is None,
    )
    if begin_clicked and definition is not None:
        st.session_state["conference_attempt"] = start_attempt(definition)
        st.rerun()

    if definition is None:
        st.info(
            "This case remains overview-only. The staged conference is "
            "available only for the linked Rutherford IIa DataHub asset."
        )


def _render_feedback(answer: AnswerRecord) -> None:
    if answer.is_correct:
        st.success(
            f"Correct — {answer.points_earned} points earned.",
            icon="✅",
        )
    else:
        st.error("Incorrect — 0 points earned.", icon="❌")

    st.markdown(f"**Your choice ({answer.choice_letter}):** {answer.choice_text}")
    st.write(answer.choice_feedback)
    st.markdown(
        f"**Correct answer ({answer.correct_choice_letter}):** "
        f"{answer.correct_choice_text}"
    )
    st.markdown(f"**Clinical rationale:** {answer.rationale}")
    st.warning(f"Safety principle: {answer.safety_principle}", icon="⚠️")


def _render_performance_report(
    definition: ConferenceDefinition,
    attempt: AttemptState,
) -> None:
    st.caption("Stage 6 of 6")
    st.title("Performance report")
    score_column, correct_column = st.columns(2)
    score_column.metric(
        "Total score",
        f"{attempt.score} / {definition.total_points}",
    )
    correct_column.metric(
        "Correct answers",
        f"{attempt.correct_answer_count} / {len(definition.stages)}",
    )
    st.progress(attempt.score / definition.total_points)

    strengths: list[str] = []
    review_topics: list[str] = []
    for stage in definition.stages:
        answer = attempt.answers[stage.id]
        result = "Correct" if answer.is_correct else "Incorrect"
        topic_list = strengths if answer.is_correct else review_topics
        topic_list.append(stage.title)
        with st.container(border=True):
            st.subheader(stage.title)
            st.write(
                f"{result} · {answer.points_earned} / {stage.points} points"
            )
            st.caption(f"Selected {answer.choice_letter}: {answer.choice_text}")
            st.caption(
                f"Correct {answer.correct_choice_letter}: "
                f"{answer.correct_choice_text}"
            )

    strengths_column, review_column = st.columns(2)
    with strengths_column:
        st.subheader("Educational strengths")
        if strengths:
            for topic in strengths:
                st.write(f"• {topic}")
        else:
            st.write("No scored strengths yet; review all five topics.")

    with review_column:
        st.subheader("Topics requiring review")
        if review_topics:
            for topic in review_topics:
                st.write(f"• {topic}")
        else:
            st.write("No scored topics require review on this attempt.")

    st.info(EDUCATIONAL_DISCLAIMER, icon="ℹ️")
    if st.button(
        "Restart Case",
        type="primary",
        use_container_width=True,
        key=f"restart-report-{attempt.attempt_id}",
    ):
        st.session_state["conference_attempt"] = restart_attempt(
            definition,
            attempt,
        )
        st.rerun()

    if st.button(
        "Return to case overview",
        use_container_width=True,
        key=f"overview-report-{attempt.attempt_id}",
    ):
        st.session_state.pop("conference_attempt", None)
        st.rerun()


def _render_case_conference(
    case: CaseAsset,
    definition: ConferenceDefinition,
    attempt: AttemptState,
) -> None:
    if attempt.is_complete:
        _render_performance_report(definition, attempt)
        return

    top_left, top_right = st.columns([3, 1])
    top_left.caption(case.title)
    if top_right.button(
        "Restart",
        use_container_width=True,
        key=f"restart-stage-{attempt.attempt_id}",
    ):
        st.session_state["conference_attempt"] = restart_attempt(
            definition,
            attempt,
        )
        st.rerun()

    stage = current_stage(definition, attempt)
    assert stage is not None
    st.caption(f"Stage {stage.number} of 6 · {stage.points} points")
    st.header(stage.title)
    st.progress((stage.number - 1) / len(definition.stages))

    if stage.number == 1:
        with st.expander("Synthetic case findings", expanded=True):
            for finding in definition.synthetic_findings:
                st.write(f"• {finding}")

    st.write(stage.narrative)
    st.subheader(stage.question)

    choices = presented_choices(definition, attempt)
    choice_labels = {
        choice.choice_id: f"{choice.letter}. {choice.text}" for choice in choices
    }
    answer = attempt.answers.get(stage.id)
    selected_choice_id = st.radio(
        "Choose one answer",
        options=list(choice_labels),
        format_func=choice_labels.__getitem__,
        index=None,
        disabled=answer is not None,
        key=f"choice-{attempt.attempt_id}-{stage.id}",
    )

    if answer is None:
        if st.button(
            "Submit answer",
            type="primary",
            use_container_width=True,
            disabled=selected_choice_id is None,
            key=f"submit-{attempt.attempt_id}-{stage.id}",
        ):
            submit_answer(
                definition,
                attempt,
                stage_id=stage.id,
                choice_id=selected_choice_id,
            )
            st.rerun()
    else:
        _render_feedback(answer)
        button_label = (
            "View Performance Report"
            if stage.number == len(definition.stages)
            else "Continue to Next Stage"
        )
        if st.button(
            button_label,
            type="primary",
            use_container_width=True,
            key=f"continue-{attempt.attempt_id}-{stage.id}",
        ):
            advance_stage(definition, attempt)
            st.rerun()


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
        st.session_state.pop("conference_attempt", None)
        _render_case_catalog(cases)
    else:
        definition = None
        if selected_case.urn == RUTHERFORD_IIA_DATAHUB_URN:
            try:
                definition = load_rutherford_iia_conference(selected_case)
            except ContentValidationError as exc:
                st.error("The staged case content failed its safety validation.")
                st.write(str(exc))

        attempt = st.session_state.get("conference_attempt")
        if attempt is None or definition is None:
            _render_case_overview(selected_case, definition)
        else:
            _render_case_conference(selected_case, definition, attempt)

    st.divider()
    st.caption(EDUCATIONAL_DISCLAIMER)


if __name__ == "__main__":
    main()
