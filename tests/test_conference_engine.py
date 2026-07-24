from __future__ import annotations

from pathlib import Path

import pytest

from vascurounds.case_urns import (
    ACUTE_LIMB_ISCHEMIA_URNS,
    RUTHERFORD_I_DATAHUB_URN,
    RUTHERFORD_IIA_DATAHUB_URN,
    RUTHERFORD_IIB_DATAHUB_URN,
    RUTHERFORD_III_DATAHUB_URN,
)
from vascurounds.conference.content import (
    CONFERENCE_BY_URN,
    ContentValidationError,
    conference_available_for_urn,
    load_conference,
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
from vascurounds.conference.models import ConferenceDefinition
from vascurounds.models import EDUCATIONAL_DISCLAIMER, CaseAsset
from vascurounds.providers.mock import MockCaseProvider


MOCK_CASES = tuple(MockCaseProvider().list_cases())
CASES_BY_URN = {case.urn: case for case in MOCK_CASES}
EXPECTED_CATEGORIES = {
    RUTHERFORD_I_DATAHUB_URN: "Rutherford I",
    RUTHERFORD_IIA_DATAHUB_URN: "Rutherford IIa",
    RUTHERFORD_IIB_DATAHUB_URN: "Rutherford IIb",
    RUTHERFORD_III_DATAHUB_URN: "Rutherford III",
}


@pytest.fixture(params=MOCK_CASES, ids=lambda case: case.rutherford_category)
def case_asset(request) -> CaseAsset:
    return request.param


@pytest.fixture
def definition(case_asset: CaseAsset) -> ConferenceDefinition:
    return load_conference(case_asset)


def _definition(urn: str) -> ConferenceDefinition:
    return load_conference(CASES_BY_URN[urn])


def _incorrect_choice_id(definition: ConferenceDefinition, stage_id: str) -> str:
    stage = definition.stage_by_id(stage_id)
    return next(choice.id for choice in stage.choices if not choice.correct)


def test_registry_contains_all_and_only_the_four_exact_datahub_urns() -> None:
    assert tuple(CONFERENCE_BY_URN) == ACUTE_LIMB_ISCHEMIA_URNS
    assert set(CONFERENCE_BY_URN) == set(EXPECTED_CATEGORIES)

    for urn, expected_category in EXPECTED_CATEGORIES.items():
        registration = CONFERENCE_BY_URN[urn]
        assert registration.urn == urn
        assert registration.rutherford_category == expected_category
        assert not registration.content_path.is_absolute() or (
            "content" in registration.content_path.parts
        )


def test_each_registered_urn_resolves_to_the_matching_conference() -> None:
    for urn, expected_category in EXPECTED_CATEGORIES.items():
        definition = _definition(urn)
        assert conference_available_for_urn(urn)
        assert definition.datahub_urn == urn
        assert definition.rutherford_category == expected_category


def test_unknown_urn_is_not_registered_and_remains_unloadable() -> None:
    unknown = CaseAsset(
        urn="urn:li:dataset:(urn:li:dataPlatform:file,unsupported,DEV)",
        title="Unsupported synthetic case",
        rutherford_category="Rutherford I",
        description="Synthetic test fixture.",
        synthetic_data=True,
        educational_use=True,
    )

    assert not conference_available_for_urn(unknown.urn)
    with pytest.raises(ContentValidationError, match="No staged conference"):
        load_conference(unknown)


def test_rutherford_iia_backward_compatible_loader_is_unchanged() -> None:
    case = CASES_BY_URN[RUTHERFORD_IIA_DATAHUB_URN]

    generic = load_conference(case)
    legacy = load_rutherford_iia_conference(case)

    assert generic == legacy
    assert [stage.correct_choice.id for stage in legacy.stages] == [
        "urgent_vascular_assessment",
        "rutherford_iia",
        "heparin_and_urgent_planning",
        "prompt_anatomic_imaging",
        "tailored_limb_salvage",
    ]


def test_every_conference_satisfies_the_validated_content_contract(
    definition: ConferenceDefinition,
) -> None:
    assert definition.disclaimer == EDUCATIONAL_DISCLAIMER
    assert len(definition.stages) == 5
    assert definition.total_points == 100
    assert [stage.number for stage in definition.stages] == [1, 2, 3, 4, 5]
    assert len({stage.id for stage in definition.stages}) == 5

    for stage in definition.stages:
        assert stage.points == 20
        assert len(stage.choices) == 4
        assert len({choice.id for choice in stage.choices}) == 4
        assert sum(choice.correct for choice in stage.choices) == 1
        assert stage.rationale
        assert stage.safety_principle
        assert all(choice.text and choice.feedback for choice in stage.choices)


def test_malformed_json_fails_with_a_clear_content_error(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not valid JSON", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="Unable to load"):
        load_conference(
            CASES_BY_URN[RUTHERFORD_I_DATAHUB_URN],
            content_path=malformed,
        )


def test_non_object_json_fails_with_a_clear_content_error(tmp_path: Path) -> None:
    malformed = tmp_path / "array.json"
    malformed.write_text("[]", encoding="utf-8")

    with pytest.raises(ContentValidationError, match="must be a JSON object"):
        load_conference(
            CASES_BY_URN[RUTHERFORD_I_DATAHUB_URN],
            content_path=malformed,
        )


def test_clinically_defining_rutherford_findings_are_distinct() -> None:
    viable = " ".join(
        _definition(RUTHERFORD_I_DATAHUB_URN).synthetic_findings
    ).casefold()
    marginal = " ".join(
        _definition(RUTHERFORD_IIA_DATAHUB_URN).synthetic_findings
    ).casefold()
    immediate = " ".join(
        _definition(RUTHERFORD_IIB_DATAHUB_URN).synthetic_findings
    ).casefold()
    irreversible = " ".join(
        _definition(RUTHERFORD_III_DATAHUB_URN).synthetic_findings
    ).casefold()

    assert "no sensory loss" in viable
    assert "no motor weakness" in viable
    assert "audible arterial doppler" in viable
    assert "audible venous doppler" in viable

    assert "limited to the toes" in marginal
    assert "no motor weakness" in marginal
    assert "absent arterial doppler" in marginal
    assert "preserved venous doppler" in marginal

    assert "beyond the toes" in immediate
    assert "motor weakness" in immediate
    assert "absent arterial doppler" in immediate
    assert "preserved venous doppler" in immediate

    assert "anesthesia" in irreversible
    assert "paralysis" in irreversible
    assert "absent arterial doppler" in irreversible
    assert "absent venous doppler" in irreversible


def test_iia_and_iib_motor_findings_cannot_be_reversed() -> None:
    marginal = _definition(RUTHERFORD_IIA_DATAHUB_URN)
    immediate = _definition(RUTHERFORD_IIB_DATAHUB_URN)

    marginal_findings = " ".join(marginal.synthetic_findings).casefold()
    immediate_findings = " ".join(immediate.synthetic_findings).casefold()
    assert "no motor weakness" in marginal_findings
    assert "motor weakness" in immediate_findings
    assert "no motor weakness" not in immediate_findings

    assert marginal.stage_by_id(
        "rutherford_classification"
    ).correct_choice.id == "rutherford_iia"
    assert immediate.stage_by_id(
        "rutherford_classification"
    ).correct_choice.id == "rutherford_iib"


def test_rutherford_iii_definitive_answer_does_not_recommend_revascularization() -> None:
    definitive = _definition(RUTHERFORD_III_DATAHUB_URN).stage_by_id(
        "definitive_management"
    )
    correct_text = definitive.correct_choice.text.casefold()

    assert definitive.correct_choice.id == "amputation_or_palliation"
    assert "amputation" in correct_text
    assert "palliation" in correct_text
    assert "revascularization" not in correct_text


def test_case_specific_management_priorities_are_present() -> None:
    viable = _definition(RUTHERFORD_I_DATAHUB_URN)
    immediately_threatened = _definition(RUTHERFORD_IIB_DATAHUB_URN)
    irreversible = _definition(RUTHERFORD_III_DATAHUB_URN)

    viable_text = " ".join(
        (
            viable.stage_by_id("immediate_management").rationale,
            viable.stage_by_id("imaging_and_planning").rationale,
            viable.stage_by_id("definitive_management").rationale,
        )
    ).casefold()
    for term in (
        "urgent vascular-surgery assessment",
        "intravenous unfractionated heparin",
        "prompt anatomical imaging",
        "etiology",
        "bleeding risk",
    ):
        assert term in viable_text

    iib_text = " ".join(
        (
            immediately_threatened.stage_by_id("focused_assessment").rationale,
            immediately_threatened.stage_by_id("immediate_management").rationale,
            immediately_threatened.stage_by_id("imaging_and_planning").rationale,
            immediately_threatened.stage_by_id(
                "definitive_management"
            ).rationale,
        )
    ).casefold()
    for term in (
        "motor weakness",
        "intravenous unfractionated heparin",
        "does not postpone reperfusion",
        "fastest appropriate",
        "time to reperfusion",
    ):
        assert term in iib_text

    iii_text = " ".join(
        (
            irreversible.stage_by_id("immediate_management").rationale,
            irreversible.stage_by_id("imaging_and_planning").rationale,
            irreversible.stage_by_id("definitive_management").rationale,
            irreversible.stage_by_id("definitive_management").safety_principle,
        )
    ).casefold()
    for term in (
        "hyperkalemia",
        "acidosis",
        "myoglobinuria",
        "renal injury",
        "primary amputation",
        "palliation",
        "systemic toxicity",
    ):
        assert term in iii_text


def test_sequential_progression_and_five_correct_answers_score_100(
    definition: ConferenceDefinition,
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
        assert answer.points_earned == 20
        assert current_stage(definition, attempt) == stage
        advance_stage(definition, attempt)

    assert attempt.is_complete
    assert current_stage(definition, attempt) is None
    assert attempt.score == 100
    assert attempt.correct_answer_count == 5


def test_skipping_and_reanswering_are_prevented(
    definition: ConferenceDefinition,
) -> None:
    attempt = start_attempt(definition, seed=23)
    first_stage = definition.stages[0]

    with pytest.raises(StageProgressionError, match="Answer the current stage"):
        advance_stage(definition, attempt)
    with pytest.raises(StageProgressionError, match="current stage"):
        submit_answer(
            definition,
            attempt,
            stage_id=definition.stages[1].id,
            choice_id=definition.stages[1].correct_choice.id,
        )

    original = submit_answer(
        definition,
        attempt,
        stage_id=first_stage.id,
        choice_id=first_stage.correct_choice.id,
    )
    with pytest.raises(StageProgressionError, match="already been answered"):
        submit_answer(
            definition,
            attempt,
            stage_id=first_stage.id,
            choice_id=_incorrect_choice_id(definition, first_stage.id),
        )
    assert attempt.answers[first_stage.id] == original


def test_deterministic_scoring_awards_20_or_zero(
    definition: ConferenceDefinition,
) -> None:
    stage = definition.stages[0]
    correct_attempt = start_attempt(definition, seed=29)
    incorrect_attempt = start_attempt(definition, seed=29)

    correct = submit_answer(
        definition,
        correct_attempt,
        stage_id=stage.id,
        choice_id=stage.correct_choice.id,
    )
    incorrect = submit_answer(
        definition,
        incorrect_attempt,
        stage_id=stage.id,
        choice_id=_incorrect_choice_id(definition, stage.id),
    )

    assert correct.points_earned == 20
    assert correct_attempt.score == 20
    assert incorrect.points_earned == 0
    assert incorrect_attempt.score == 0


def test_randomization_preserves_stable_answer_ids_and_correctness(
    definition: ConferenceDefinition,
) -> None:
    first = start_attempt(definition, seed=31)
    same_seed = start_attempt(definition, seed=31)
    second = start_attempt(definition, seed=47)

    assert first.option_orders == same_seed.option_orders
    assert first.option_orders != second.option_orders

    correct_letters: set[str] = set()
    for stage in definition.stages:
        expected_ids = {choice.id for choice in stage.choices}
        assert set(first.option_orders[stage.id]) == expected_ids
        assert set(second.option_orders[stage.id]) == expected_ids
        correct_letters.add(
            "ABCD"[first.option_orders[stage.id].index(stage.correct_choice.id)]
        )

    assert len(correct_letters) > 1


def test_restart_resets_everything_and_reshuffles_every_stage(
    definition: ConferenceDefinition,
) -> None:
    attempt = start_attempt(definition, seed=59)
    stage = definition.stages[0]
    submit_answer(
        definition,
        attempt,
        stage_id=stage.id,
        choice_id=stage.correct_choice.id,
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


def test_report_calculations_match_submitted_answers(
    definition: ConferenceDefinition,
) -> None:
    attempt = start_attempt(definition, seed=71)

    for stage in definition.stages:
        choice_id = (
            stage.correct_choice.id
            if stage.number <= 3
            else _incorrect_choice_id(definition, stage.id)
        )
        submit_answer(
            definition,
            attempt,
            stage_id=stage.id,
            choice_id=choice_id,
        )
        advance_stage(definition, attempt)

    assert attempt.is_complete
    assert attempt.score == 60
    assert attempt.correct_answer_count == 3
    assert [answer.points_earned for answer in attempt.answers.values()] == [
        20,
        20,
        20,
        0,
        0,
    ]


def test_attempts_are_isolated_between_conferences() -> None:
    viable = _definition(RUTHERFORD_I_DATAHUB_URN)
    marginal = _definition(RUTHERFORD_IIA_DATAHUB_URN)
    viable_attempt = start_attempt(viable, seed=79)
    marginal_attempt = start_attempt(marginal, seed=83)

    submit_answer(
        viable,
        viable_attempt,
        stage_id=viable.stages[0].id,
        choice_id=viable.stages[0].correct_choice.id,
    )

    assert viable_attempt.score == 20
    assert marginal_attempt.score == 0
    assert marginal_attempt.answers == {}
    assert viable_attempt.option_orders != marginal_attempt.option_orders
    with pytest.raises(StageProgressionError, match="not linked"):
        current_stage(marginal, viable_attempt)

    restarted_viable = restart_attempt(viable, viable_attempt, seed=79)
    assert restarted_viable.score == 0
    assert marginal_attempt.option_orders == start_attempt(
        marginal,
        seed=83,
    ).option_orders
