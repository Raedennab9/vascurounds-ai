from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from vascurounds.case_urns import (
    RUTHERFORD_I_DATAHUB_URN,
    RUTHERFORD_IIA_DATAHUB_URN,
    RUTHERFORD_IIB_DATAHUB_URN,
    RUTHERFORD_III_DATAHUB_URN,
)
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


CONTENT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "content"
    / "acute_limb_ischemia"
)

@dataclass(frozen=True, slots=True)
class ConferenceRegistration:
    urn: str
    rutherford_category: str
    content_path: Path


CONFERENCE_BY_URN: dict[str, ConferenceRegistration] = {
    RUTHERFORD_I_DATAHUB_URN: ConferenceRegistration(
        urn=RUTHERFORD_I_DATAHUB_URN,
        rutherford_category="Rutherford I",
        content_path=CONTENT_ROOT / "rutherford_i.json",
    ),
    RUTHERFORD_IIA_DATAHUB_URN: ConferenceRegistration(
        urn=RUTHERFORD_IIA_DATAHUB_URN,
        rutherford_category="Rutherford IIa",
        content_path=CONTENT_ROOT / "rutherford_iia.json",
    ),
    RUTHERFORD_IIB_DATAHUB_URN: ConferenceRegistration(
        urn=RUTHERFORD_IIB_DATAHUB_URN,
        rutherford_category="Rutherford IIb",
        content_path=CONTENT_ROOT / "rutherford_iib.json",
    ),
    RUTHERFORD_III_DATAHUB_URN: ConferenceRegistration(
        urn=RUTHERFORD_III_DATAHUB_URN,
        rutherford_category="Rutherford III",
        content_path=CONTENT_ROOT / "rutherford_iii.json",
    ),
}

DEFAULT_IIA_CONTENT_PATH = CONFERENCE_BY_URN[
    RUTHERFORD_IIA_DATAHUB_URN
].content_path


class ContentValidationError(ValueError):
    """Raised when local conference content violates the content contract."""


def conference_available_for_urn(urn: str) -> bool:
    return urn in CONFERENCE_BY_URN


def load_conference(
    case_asset: CaseAsset,
    content_path: Path | None = None,
) -> ConferenceDefinition:
    registration = CONFERENCE_BY_URN.get(case_asset.urn)
    if registration is None:
        raise ContentValidationError(
            f"No staged conference is registered for DataHub URN {case_asset.urn!r}."
        )
    if not case_asset.synthetic_data or not case_asset.educational_use:
        raise ContentValidationError(
            "Conference content can only be linked to a confirmed synthetic "
            "educational DataHub asset."
        )

    category = normalize_rutherford_category(case_asset.rutherford_category)
    if category != registration.rutherford_category:
        raise ContentValidationError(
            "The selected DataHub asset category does not match its conference "
            f"registration: expected {registration.rutherford_category!r}."
        )

    path = content_path or registration.content_path
    raw = _load_json_object(path)
    link = raw.get("datahub_link")
    if not isinstance(link, dict):
        raise ContentValidationError(
            "Conference content must include a datahub_link object."
        )
    if link.get("urn") != registration.urn:
        raise ContentValidationError(
            "Conference content DataHub URN does not match its registry entry."
        )
    if link.get("required_category") != category:
        raise ContentValidationError(
            "Conference content category does not match the selected DataHub asset."
        )
    if raw.get("rutherford_category") != category:
        raise ContentValidationError(
            "Conference Rutherford category does not match its DataHub link."
        )
    if raw.get("disclaimer") != EDUCATIONAL_DISCLAIMER:
        raise ContentValidationError("The required educational disclaimer is missing.")

    raw_stages = raw.get("stages")
    if not isinstance(raw_stages, list):
        raise ContentValidationError("Conference stages must be a JSON array.")

    stages = tuple(_parse_stage(stage) for stage in raw_stages)
    raw_findings = raw.get("synthetic_findings")
    if not isinstance(raw_findings, list):
        raise ContentValidationError("Synthetic findings must be a JSON array.")

    definition = ConferenceDefinition(
        id=_string_value(raw, "id"),
        title=_string_value(raw, "title"),
        rutherford_category=category,
        datahub_urn=registration.urn,
        disclaimer=EDUCATIONAL_DISCLAIMER,
        synthetic_findings=tuple(
            finding.strip()
            for finding in raw_findings
            if isinstance(finding, str) and finding.strip()
        ),
        stages=stages,
    )
    _validate_definition(definition)
    return definition


def load_rutherford_iia_conference(
    case_asset: CaseAsset,
    content_path: Path | None = None,
) -> ConferenceDefinition:
    """Backward-compatible wrapper for the validated Rutherford IIa case."""

    if case_asset.urn != RUTHERFORD_IIA_DATAHUB_URN:
        raise ContentValidationError(
            "The staged conference is linked only to the approved Rutherford "
            "IIa DataHub asset URN."
        )
    return load_conference(case_asset, content_path)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as content_file:
            raw = json.load(content_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContentValidationError(
            f"Unable to load conference content from {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ContentValidationError(
            f"Conference content in {path} must be a JSON object."
        )
    return raw


def _parse_stage(raw: Any) -> StageDefinition:
    if not isinstance(raw, dict):
        raise ContentValidationError("Every conference stage must be a JSON object.")
    raw_choices = raw.get("choices")
    if not isinstance(raw_choices, list):
        raise ContentValidationError(
            f"Stage {_string_value(raw, 'id')!r} choices must be a JSON array."
        )

    number = raw.get("number")
    points = raw.get("points")
    if not isinstance(number, int) or isinstance(number, bool):
        raise ContentValidationError("Stage number must be an integer.")
    if not isinstance(points, int) or isinstance(points, bool):
        raise ContentValidationError("Stage points must be an integer.")

    return StageDefinition(
        id=_string_value(raw, "id"),
        number=number,
        title=_string_value(raw, "title"),
        narrative=_string_value(raw, "narrative"),
        question=_string_value(raw, "question"),
        points=points,
        rationale=_string_value(raw, "rationale"),
        safety_principle=_string_value(raw, "safety_principle"),
        choices=tuple(_parse_choice(choice) for choice in raw_choices),
    )


def _parse_choice(raw: Any) -> ChoiceDefinition:
    if not isinstance(raw, dict):
        raise ContentValidationError("Every answer choice must be a JSON object.")
    correct = raw.get("correct")
    if not isinstance(correct, bool):
        raise ContentValidationError("Choice correct must be a JSON boolean.")
    return ChoiceDefinition(
        id=_string_value(raw, "id"),
        text=_string_value(raw, "text"),
        correct=correct,
        feedback=_string_value(raw, "feedback"),
    )


def _string_value(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    return value.strip() if isinstance(value, str) else ""


def _validate_definition(definition: ConferenceDefinition) -> None:
    if not definition.id or not definition.title or not definition.datahub_urn:
        raise ContentValidationError(
            "Conference ID, title, and DataHub URN are required."
        )
    if not definition.synthetic_findings:
        raise ContentValidationError(
            "At least one synthetic clinical finding is required."
        )
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
        required_stage_text = (
            stage.id,
            stage.title,
            stage.narrative,
            stage.question,
            stage.rationale,
            stage.safety_principle,
        )
        if not all(value for value in required_stage_text):
            raise ContentValidationError(
                f"Stage {stage.id!r} is missing required educational content."
            )
        for choice in stage.choices:
            if not choice.id or not choice.text or not choice.feedback:
                raise ContentValidationError(
                    f"Stage {stage.id!r} has an incomplete answer choice."
                )
