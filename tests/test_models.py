from __future__ import annotations

from vascurounds.models import (
    EDUCATIONAL_DISCLAIMER,
    EDUCATIONAL_STATUS_LABEL,
    SYNTHETIC_STATUS_LABEL,
    CaseAsset,
    sort_cases_clinically,
)


def _case(category: str) -> CaseAsset:
    return CaseAsset(
        urn=f"urn:test:{category}",
        title=category,
        rutherford_category=category,
        description="Synthetic test case.",
        synthetic_data=True,
        educational_use=True,
    )


def test_cases_are_sorted_in_clinical_order() -> None:
    cases = [_case("Rutherford III"), _case("Rutherford IIb"), _case("Rutherford I")]
    cases.append(_case("Rutherford IIa"))

    assert [case.rutherford_category for case in sort_cases_clinically(cases)] == [
        "Rutherford I",
        "Rutherford IIa",
        "Rutherford IIb",
        "Rutherford III",
    ]


def test_required_safety_labels_and_disclaimer_are_preserved() -> None:
    case = _case("Rutherford I")

    assert case.safety_labels == (
        SYNTHETIC_STATUS_LABEL,
        EDUCATIONAL_STATUS_LABEL,
    )
    assert EDUCATIONAL_DISCLAIMER == (
        "For professional education and simulation only. "
        "Not for direct patient-care decision-making."
    )
