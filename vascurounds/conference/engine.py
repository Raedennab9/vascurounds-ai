from __future__ import annotations

import random
import secrets
import uuid

from vascurounds.conference.models import (
    AnswerRecord,
    AttemptState,
    ConferenceDefinition,
    PresentedChoice,
    StageDefinition,
)


OPTION_LETTERS = ("A", "B", "C", "D")


class StageProgressionError(RuntimeError):
    """Raised when an attempt tries to answer or advance out of sequence."""


class InvalidAnswerError(ValueError):
    """Raised when a submitted choice does not belong to the current stage."""


def start_attempt(
    definition: ConferenceDefinition,
    *,
    seed: int | None = None,
    previous_orders: dict[str, tuple[str, ...]] | None = None,
) -> AttemptState:
    attempt_seed = secrets.randbits(64) if seed is None else seed
    orders = _build_option_orders(definition, attempt_seed, previous_orders)
    return AttemptState(
        attempt_id=uuid.uuid4().hex,
        case_id=definition.id,
        datahub_urn=definition.datahub_urn,
        seed=attempt_seed,
        stage_count=len(definition.stages),
        option_orders=orders,
    )


def restart_attempt(
    definition: ConferenceDefinition,
    previous_attempt: AttemptState,
    *,
    seed: int | None = None,
) -> AttemptState:
    _validate_attempt_link(definition, previous_attempt)
    return start_attempt(
        definition,
        seed=seed,
        previous_orders=previous_attempt.option_orders,
    )


def current_stage(
    definition: ConferenceDefinition,
    attempt: AttemptState,
) -> StageDefinition | None:
    _validate_attempt_link(definition, attempt)
    if attempt.is_complete:
        return None
    return definition.stages[attempt.current_stage_index]


def presented_choices(
    definition: ConferenceDefinition,
    attempt: AttemptState,
) -> tuple[PresentedChoice, ...]:
    stage = current_stage(definition, attempt)
    if stage is None:
        return ()
    return tuple(
        PresentedChoice(
            letter=OPTION_LETTERS[index],
            choice_id=choice_id,
            text=stage.choice_by_id(choice_id).text,
        )
        for index, choice_id in enumerate(attempt.option_orders[stage.id])
    )


def submit_answer(
    definition: ConferenceDefinition,
    attempt: AttemptState,
    *,
    stage_id: str,
    choice_id: str,
) -> AnswerRecord:
    stage = current_stage(definition, attempt)
    if stage is None:
        raise StageProgressionError("The attempt is already complete.")
    if stage.id != stage_id:
        raise StageProgressionError(
            f"Cannot answer stage {stage_id!r}; current stage is {stage.id!r}."
        )
    if stage.id in attempt.answers:
        raise StageProgressionError("The current stage has already been answered.")

    order = attempt.option_orders[stage.id]
    if choice_id not in order:
        raise InvalidAnswerError(
            f"Choice {choice_id!r} does not belong to stage {stage.id!r}."
        )

    choice = stage.choice_by_id(choice_id)
    correct_choice = stage.correct_choice
    record = AnswerRecord(
        stage_id=stage.id,
        choice_id=choice.id,
        choice_letter=OPTION_LETTERS[order.index(choice.id)],
        choice_text=choice.text,
        choice_feedback=choice.feedback,
        correct_choice_id=correct_choice.id,
        correct_choice_letter=OPTION_LETTERS[order.index(correct_choice.id)],
        correct_choice_text=correct_choice.text,
        is_correct=choice.correct,
        points_earned=stage.points if choice.correct else 0,
        rationale=stage.rationale,
        safety_principle=stage.safety_principle,
    )
    attempt.answers[stage.id] = record
    return record


def advance_stage(
    definition: ConferenceDefinition,
    attempt: AttemptState,
) -> None:
    stage = current_stage(definition, attempt)
    if stage is None:
        raise StageProgressionError("The attempt is already at the performance report.")
    if stage.id not in attempt.answers:
        raise StageProgressionError("Answer the current stage before continuing.")
    attempt.current_stage_index += 1


def _build_option_orders(
    definition: ConferenceDefinition,
    seed: int,
    previous_orders: dict[str, tuple[str, ...]] | None,
) -> dict[str, tuple[str, ...]]:
    generator = random.Random(seed)
    orders: dict[str, tuple[str, ...]] = {}
    for stage in definition.stages:
        choice_ids = [choice.id for choice in stage.choices]
        generator.shuffle(choice_ids)
        orders[stage.id] = tuple(choice_ids)

    if previous_orders:
        for stage in definition.stages:
            if orders.get(stage.id) == previous_orders.get(stage.id):
                orders[stage.id] = _rotate(orders[stage.id])

    correct_positions = [
        orders[stage.id].index(stage.correct_choice.id) for stage in definition.stages
    ]
    if len(set(correct_positions)) == 1 and len(definition.stages) > 1:
        stage = definition.stages[1]
        order = list(orders[stage.id])
        correct_index = order.index(stage.correct_choice.id)
        swap_index = (correct_index + 1) % len(order)
        order[correct_index], order[swap_index] = order[swap_index], order[correct_index]
        orders[stage.id] = tuple(order)

    return orders


def _rotate(order: tuple[str, ...]) -> tuple[str, ...]:
    return order[1:] + order[:1]


def _validate_attempt_link(
    definition: ConferenceDefinition,
    attempt: AttemptState,
) -> None:
    if attempt.case_id != definition.id or attempt.datahub_urn != definition.datahub_urn:
        raise StageProgressionError(
            "Attempt is not linked to this DataHub-backed case definition."
        )
