from __future__ import annotations

import pytest

from vascurounds.conference.content import (
    ContentValidationError,
    RUTHERFORD_IIA_DATAHUB_URN,
    load_rutherford_iia_conference,
)
from vascurounds.conference.engine import (
    StageProgressionError,
    advance_stage,
    current_stage,
    presented_choices,
    restart_attempt,
    start_attempt,
    submit_answer,
)
from vascurounds.models import EDUCATIONAL_DISCLAIMER, CaseAsset


IIA_DATAHUB_URN = RUTHERFORD_IIA_DATAHUB_URN


@pytest.fixture
def iia_case() -> CaseAsset:
    return CaseAsset(
        urn=IIA_DATAHUB_URN,
        title="Rutherford IIa — Marginally Threatened",
        rutherford_category="Rutherford IIa",
        description="A synthetic educational Rutherford IIa case.",
        synthetic_data=True,
        educational_use=True,
    )


@pytest.fixture
def definition(iia_case: CaseAsset):
    return load_rutherford_iia_conference(iia_case)


def _correct_choice_id(definition, stage_id: str) -> str:
    return definition.stage_by_id(stage_id).correct_choice.id


def test_stage_progression_requires_each_answer_and_reaches_report(
    definition,
) -> None:
    attempt = start_attempt(definition, seed=17)

    for expected_index, stage in enumerate(definition.stages):
        assert attempt.current_stage_index == expected_index
        assert current_stage(definition, attempt) == stage

        answer = submit_answer(
            definition,
            attempt,
            stage_id=stage.id,
            choice_id=stage.correct_choice.id,
        )
        assert answer.is_correct
        assert current_stage(definition, attempt) == stage

        advance_stage(definition, attempt)

    assert attempt.is_complete
    assert current_stage(definition, attempt) is None
    assert attempt.score == 100


def test_deterministic_scoring_uses_explicit_stage_points(definition) -> None:
    assert [stage.points for stage in definition.stages] == [20, 20, 20, 20, 20]
    assert definition.total_points == 100

    attempt = start_attempt(definition, seed=23)
    first_stage = definition.stages[0]
    submit_answer(
        definition,
        attempt,
        stage_id=first_stage.id,
        choice_id=first_stage.correct_choice.id,
    )
    advance_stage(definition, attempt)

    second_stage = definition.stages[1]
    incorrect_choice = next(
        choice for choice in second_stage.choices if not choice.correct
    )
    answer = submit_answer(
        definition,
        attempt,
        stage_id=second_stage.id,
        choice_id=incorrect_choice.id,
    )

    assert attempt.score == 20
    assert answer.points_earned == 0
    assert answer.choice_feedback
    assert answer.correct_choice_id == second_stage.correct_choice.id
    assert answer.correct_choice_letter in {"A", "B", "C", "D"}
    assert answer.correct_choice_text == second_stage.correct_choice.text
    assert answer.rationale
    assert answer.safety_principle


def test_option_randomization_preserves_ids_and_varies_correct_letters(
    definition,
) -> None:
    first = start_attempt(definition, seed=31)
    same_seed = start_attempt(definition, seed=31)
    second = start_attempt(definition, seed=47)

    assert first.option_orders == same_seed.option_orders
    assert first.option_orders != second.option_orders

    for stage in definition.stages:
        expected_ids = {choice.id for choice in stage.choices}
        assert set(first.option_orders[stage.id]) == expected_ids

    correct_letters: set[str] = set()
    for stage in definition.stages:
        attempt = start_attempt(definition, seed=31)
        attempt.current_stage_index = stage.number - 1
        displayed = presented_choices(definition, attempt)
        correct_letters.add(
            next(
                choice.letter
                for choice in displayed
                if choice.choice_id == stage.correct_choice.id
            )
        )

    assert len(correct_letters) > 1


def test_restart_resets_score_progress_and_changes_option_order(definition) -> None:
    attempt = start_attempt(definition, seed=59)
    stage = definition.stages[0]
    submit_answer(
        definition,
        attempt,
        stage_id=stage.id,
        choice_id=_correct_choice_id(definition, stage.id),
    )
    advance_stage(definition, attempt)

    restarted = restart_attempt(definition, attempt, seed=59)

    assert restarted.attempt_id != attempt.attempt_id
    assert restarted.current_stage_index == 0
    assert restarted.answers == {}
    assert restarted.score == 0
    assert restarted.correct_answer_count == 0
    assert all(
        restarted.option_orders[stage.id] != attempt.option_orders[stage.id]
        for stage in definition.stages
    )


def test_attempt_cannot_skip_or_answer_stages_out_of_sequence(definition) -> None:
    attempt = start_attempt(definition, seed=61)

    with pytest.raises(StageProgressionError, match="Answer the current stage"):
        advance_stage(definition, attempt)

    with pytest.raises(StageProgressionError, match="current stage"):
        submit_answer(
            definition,
            attempt,
            stage_id=definition.stages[1].id,
            choice_id=definition.stages[1].correct_choice.id,
        )


def test_submitted_answer_is_locked(definition) -> None:
    attempt = start_attempt(definition, seed=67)
    stage = definition.stages[0]
    original = submit_answer(
        definition,
        attempt,
        stage_id=stage.id,
        choice_id=stage.correct_choice.id,
    )
    alternate = next(choice for choice in stage.choices if not choice.correct)

    with pytest.raises(StageProgressionError, match="already been answered"):
        submit_answer(
            definition,
            attempt,
            stage_id=stage.id,
            choice_id=alternate.id,
        )

    assert attempt.answers[stage.id] == original
    assert attempt.score == 20


def test_final_score_and_correct_count_are_calculated_without_an_llm(
    definition,
) -> None:
    attempt = start_attempt(definition, seed=71)

    for stage in definition.stages:
        choice = (
            stage.correct_choice
            if stage.number <= 3
            else next(choice for choice in stage.choices if not choice.correct)
        )
        submit_answer(
            definition,
            attempt,
            stage_id=stage.id,
            choice_id=choice.id,
        )
        advance_stage(definition, attempt)

    assert attempt.is_complete
    assert attempt.score == 60
    assert attempt.correct_answer_count == 3


def test_other_iia_urn_cannot_load_the_staged_content(iia_case: CaseAsset) -> None:
    other_iia_case = CaseAsset(
        urn="urn:li:dataset:(urn:li:dataPlatform:file,other-iia,DEV)",
        title=iia_case.title,
        rutherford_category=iia_case.rutherford_category,
        description=iia_case.description,
        synthetic_data=True,
        educational_use=True,
    )

    with pytest.raises(ContentValidationError, match="approved Rutherford IIa"):
        load_rutherford_iia_conference(other_iia_case)


def test_content_preserves_disclaimer_and_runtime_datahub_urn(
    definition,
) -> None:
    assert definition.disclaimer == EDUCATIONAL_DISCLAIMER
    assert definition.datahub_urn == IIA_DATAHUB_URN
    assert definition.rutherford_category == "Rutherford IIa"
    assert definition.synthetic_findings == (
        "Sudden unilateral lower-limb pain",
        "Mild sensory loss limited to the toes",
        "No motor weakness",
        "Absent arterial Doppler signal",
        "Preserved venous Doppler signal",
        "Limb salvageable with prompt treatment",
    )

    immediate_management = definition.stage_by_id("immediate_management")
    immediate_text = " ".join(
        (
            immediate_management.rationale,
            immediate_management.correct_choice.text,
        )
    ).casefold()
    for expected_principle in (
        "urgent vascular-surgery assessment",
        "intravenous unfractionated heparin",
        "analgesia and supportive care",
        "prompt anatomical imaging",
        "repeated neurological and vascular reassessment",
    ):
        assert expected_principle in immediate_text

    definitive_text = " ".join(
        (
            definition.stage_by_id("definitive_management").rationale,
            definition.stage_by_id(
                "definitive_management"
            ).correct_choice.text,
        )
    ).casefold()
    for modality in (
        "catheter-directed thrombolysis",
        "mechanical thrombectomy",
        "surgical thromboembolectomy",
        "bypass",
        "hybrid",
    ):
        assert modality in definitive_text
