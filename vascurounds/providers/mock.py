from __future__ import annotations

from vascurounds.models import CaseAsset, sort_cases_clinically


class MockCaseProvider:
    @property
    def fallback_active(self) -> bool:
        return False

    def list_cases(self) -> list[CaseAsset]:
        cases = [
            CaseAsset(
                urn="urn:li:dataset:(urn:li:dataPlatform:vascurounds,ali-iii,DEV)",
                title="Rutherford III — Irreversible",
                rutherford_category="Rutherford III",
                description=(
                    "A synthetic educational presentation with profound sensory "
                    "and motor loss and absent arterial and venous Doppler signals."
                ),
                synthetic_data=True,
                educational_use=True,
            ),
            CaseAsset(
                urn="urn:li:dataset:(urn:li:dataPlatform:vascurounds,ali-i,DEV)",
                title="Rutherford I — Viable",
                rutherford_category="Rutherford I",
                description=(
                    "A synthetic educational presentation with preserved sensation "
                    "and motor function and audible Doppler signals."
                ),
                synthetic_data=True,
                educational_use=True,
            ),
            CaseAsset(
                urn="urn:li:dataset:(urn:li:dataPlatform:vascurounds,ali-iib,DEV)",
                title="Rutherford IIb — Immediately Threatened",
                rutherford_category="Rutherford IIb",
                description=(
                    "A synthetic educational presentation with sensory loss beyond "
                    "the toes and mild-to-moderate motor weakness."
                ),
                synthetic_data=True,
                educational_use=True,
            ),
            CaseAsset(
                urn=(
                    "urn:li:dataset:(urn:li:dataPlatform:file,"
                    "vascurounds.synthetic_cases.ali_marginally_threatened,DEV)"
                ),
                title="Rutherford IIa — Marginally Threatened",
                rutherford_category="Rutherford IIa",
                description=(
                    "A synthetic educational presentation with limited sensory "
                    "change and preserved motor function."
                ),
                synthetic_data=True,
                educational_use=True,
            ),
        ]
        return sort_cases_clinically(cases)
