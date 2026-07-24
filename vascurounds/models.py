from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


EDUCATIONAL_DISCLAIMER = (
    "For professional education and simulation only. "
    "Not for direct patient-care decision-making."
)

SYNTHETIC_STATUS_LABEL = "Synthetic data: Confirmed"
EDUCATIONAL_STATUS_LABEL = "Educational use: Confirmed"
NO_PATIENT_DATA_LABEL = "Real patient information: None"
NO_DECISION_SUPPORT_LABEL = "Direct clinical decision support: Not provided"

_CATEGORY_ORDER = {
    "I": 0,
    "IIA": 1,
    "IIB": 2,
    "III": 3,
}

_CATEGORY_LABELS = {
    "I": "Rutherford I",
    "IIA": "Rutherford IIa",
    "IIB": "Rutherford IIb",
    "III": "Rutherford III",
}


@dataclass(frozen=True, slots=True)
class CaseAsset:
    urn: str
    title: str
    rutherford_category: str
    description: str
    synthetic_data: bool
    educational_use: bool

    @property
    def safety_labels(self) -> tuple[str, ...]:
        labels: list[str] = []
        if self.synthetic_data:
            labels.append(SYNTHETIC_STATUS_LABEL)
        if self.educational_use:
            labels.append(EDUCATIONAL_STATUS_LABEL)
        if self.synthetic_data and self.educational_use:
            labels.extend(
                (
                    NO_PATIENT_DATA_LABEL,
                    NO_DECISION_SUPPORT_LABEL,
                )
            )
        return tuple(labels)


def normalize_rutherford_category(value: str) -> str | None:
    normalized = value.upper()
    for label in ("RUTHERFORD", "CATEGORY", "CLASS"):
        normalized = normalized.replace(label, " ")
    tokens = re.findall(r"[A-Z0-9]+", normalized)

    for code in ("IIA", "IIB", "III", "I"):
        if code in tokens:
            return _CATEGORY_LABELS[code]
    return None


def rutherford_sort_key(case: CaseAsset) -> tuple[int, str]:
    normalized = normalize_rutherford_category(case.rutherford_category)
    if normalized is None:
        return (len(_CATEGORY_ORDER), case.title.casefold())

    code = normalized.replace("Rutherford ", "").upper()
    return (_CATEGORY_ORDER[code], case.title.casefold())


def sort_cases_clinically(cases: Iterable[CaseAsset]) -> list[CaseAsset]:
    return sorted(cases, key=rutherford_sort_key)
