from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vascurounds.conference.models import (
    ChoiceDefinition,
    ConferenceDefinition,
    StageDefinition,
)
from vascurounds.models import (
    EDUCATIONAL_DISCLAIMER,
    CaseAsset,
    normalize_rutherford_category,
)


DEFAULT_IIA_CONTENT_PATH = (
    Path(__file__).resolve().parents[2]
    / "content"
    / "acute_limb_ischemia"
    / "rutherford_iia.json"
)
RUTHERFORD_IIA_DATAHUB_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:file,"
    "vascurounds.synthetic_cases.ali_marginally_threatened,DEV)"
)


class ContentValidationError(ValueError):
    """Raised when local conference content violates the milestone contract."""


def load_rutherford_iia_conference(
    case_asset: CaseAsset,
    content_path: Path | None = None,
) -> ConferenceDefinition:
    if case_asset.urn != RUTHERFORD_IIA_DATAHUB_URN:
        raise ContentValidationError(
            "The staged conference is linked only to the approved Rutherford "
            "IIa DataHub asset URN."
        )
    if not case_asset.synthetic_data or not case_asset.educational_use:
        raise ContentValidationError(
            "Conference content can only be linked to a confirmed synthetic "
            "educational DataHub asset."
        )

    category = normalize_rutherford_category(case_asset.rutherford_category)
    if category != "Rutherford IIa":
        raise ContentValidationError(
            "The staged milestone is available only for the Rutherford IIa asset."
        )

    path = content_path or DEFAULT_IIA_CONTENT_PATH
    with path.open(encoding="utf-8") as content_file:
        raw: dict[str, Any] = json.load(content_file)

    link = raw.get("datahub_link") or {}
    if link.get("urn") != RUTHERFORD_IIA_DATAHUB_URN:
        raise ContentValidationError(
            "Conference content must declare the approved Rutherford IIa "
            "DataHub asset URN."
        )
    if link.get("required_category") != category:
        raise ContentValidationError(
            "Conference content category does not match the selected DataHub asset."
        )
    if raw.get("disclaimer") != EDUCATIONAL_DISCLAIMER:
        raise ContentValidationError("The required educational disclaimer is missing.")

    stages = tuple(_parse_stage(stage) for stage in raw.get("stages", []))
    definition = ConferenceDefinition(
        id=str(raw.get("id", "")),
        title=str(raw.get("title", "")),
        rutherford_category=category,
        datahub_urn=RUTHERFORD_IIA_DATAHUB_URN,
        disclaimer=EDUCATIONAL_DISCLAIMER,
        synthetic_findings=tuple(str(item) for item in raw.get("synthetic_findings", [])),
        stages=stages,
    )
    _validate_definition(definition)
    return definition


def _parse_stage(raw: dict[str, Any]) -> StageDefinition:
    choices = tuple(
        ChoiceDefinition(
            id=str(choice.get("id", "")),
            text=str(choice.get("text", "")),
            correct=bool(choice.get("correct", False)),
            feedback=str(choice.get("feedback", "")),
        )
        for choice in raw.get("choices", [])
    )
    return StageDefinition(
        id=str(raw.get("id", "")),
        number=int(raw.get("number", 0)),
        title=str(raw.get("title", "")),
        narrative=str(raw.get("narrative", "")),
        question=str(raw.get("question", "")),
        points=int(raw.get("points", 0)),
        rationale=str(raw.get("rationale", "")),
        safety_principle=str(raw.get("safety_principle", "")),
        choices=choices,
    )


def _validate_definition(definition: ConferenceDefinition) -> None:
    if not definition.id or not definition.datahub_urn:
        raise ContentValidationError("Conference ID and DataHub URN are required.")
    if len(definition.stages) != 5:
        raise ContentValidationError("Exactly five scored clinical stages are required.")
    if definition.total_points != 100:
        raise ContentValidationError("Clinical stage points must total 100.")
    if any(stage.points != 20 for stage in definition.stages):
        raise ContentValidationError(
            "Each of the five clinical stages must award exactly 20 points."
        )
    if len(set(stage.id for stage in definition.stages)) != len(definition.stages):
        raise ContentValidationError("Stage IDs must be unique.")

    for expected_number, stage in enumerate(definition.stages, start=1):
        if stage.number != expected_number:
            raise ContentValidationError("Stage numbers must be sequential.")
        if stage.points <= 0:
            raise ContentValidationError("Every clinical stage must award points.")
        if len(stage.choices) != 4:
            raise ContentValidationError(
                f"Stage {stage.id!r} must contain exactly four choices."
            )
        if len(set(choice.id for choice in stage.choices)) != 4:
            raise ContentValidationError(
                f"Stage {stage.id!r} choice IDs must be unique."
            )
        if sum(choice.correct for choice in stage.choices) != 1:
            raise ContentValidationError(
                f"Stage {stage.id!r} must contain exactly one correct choice."
            )
        required_text = (
            stage.title,
            stage.narrative,
            stage.question,
            stage.rationale,
            stage.safety_principle,
        )
        if not all(value.strip() for value in required_text):
            raise ContentValidationError(
                f"Stage {stage.id!r} is missing required educational content."
            )
