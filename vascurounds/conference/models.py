from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ChoiceDefinition:
    id: str
    text: str
    correct: bool
    feedback: str


@dataclass(frozen=True, slots=True)
class StageDefinition:
    id: str
    number: int
    title: str
    narrative: str
    question: str
    points: int
    rationale: str
    safety_principle: str
    choices: tuple[ChoiceDefinition, ...]

    @property
    def correct_choice(self) -> ChoiceDefinition:
        return next(choice for choice in self.choices if choice.correct)

    def choice_by_id(self, choice_id: str) -> ChoiceDefinition:
        try:
            return next(choice for choice in self.choices if choice.id == choice_id)
        except StopIteration as exc:
            raise KeyError(f"Unknown choice {choice_id!r} for stage {self.id!r}.") from exc


@dataclass(frozen=True, slots=True)
class ConferenceDefinition:
    id: str
    title: str
    rutherford_category: str
    datahub_urn: str
    disclaimer: str
    synthetic_findings: tuple[str, ...]
    stages: tuple[StageDefinition, ...]

    @property
    def total_points(self) -> int:
        return sum(stage.points for stage in self.stages)

    def stage_by_id(self, stage_id: str) -> StageDefinition:
        try:
            return next(stage for stage in self.stages if stage.id == stage_id)
        except StopIteration as exc:
            raise KeyError(f"Unknown stage {stage_id!r}.") from exc


@dataclass(frozen=True, slots=True)
class PresentedChoice:
    letter: str
    choice_id: str
    text: str


@dataclass(frozen=True, slots=True)
class AnswerRecord:
    stage_id: str
    choice_id: str
    choice_letter: str
    choice_text: str
    choice_feedback: str
    correct_choice_id: str
    correct_choice_letter: str
    correct_choice_text: str
    is_correct: bool
    points_earned: int
    rationale: str
    safety_principle: str


@dataclass(slots=True)
class AttemptState:
    attempt_id: str
    case_id: str
    datahub_urn: str
    seed: int
    stage_count: int
    option_orders: dict[str, tuple[str, ...]]
    current_stage_index: int = 0
    answers: dict[str, AnswerRecord] = field(default_factory=dict)

    @property
    def score(self) -> int:
        return sum(answer.points_earned for answer in self.answers.values())

    @property
    def correct_answer_count(self) -> int:
        return sum(answer.is_correct for answer in self.answers.values())

    @property
    def is_complete(self) -> bool:
        return self.current_stage_index >= self.stage_count
