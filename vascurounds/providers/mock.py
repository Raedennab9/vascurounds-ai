from __future__ import annotations

from vascurounds.case_urns import (
    RUTHERFORD_I_DATAHUB_URN,
    RUTHERFORD_IIA_DATAHUB_URN,
    RUTHERFORD_IIB_DATAHUB_URN,
    RUTHERFORD_III_DATAHUB_URN,
)
from vascurounds.models import CaseAsset, sort_cases_clinically
from vascurounds.providers.base import ProviderStatus


class MockCaseProvider:
    @property
    def fallback_active(self) -> bool:
        return False

    @property
    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_name="mock",
            datahub_connected=False,
            fallback_used=False,
            required_connection_failed=False,
            status_message=(
                "Explicit offline mock mode is active; DataHub was not queried."
            ),
        )

    def list_cases(self) -> list[CaseAsset]:
        cases = [
            CaseAsset(
                urn=RUTHERFORD_III_DATAHUB_URN,
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
                urn=RUTHERFORD_I_DATAHUB_URN,
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
                urn=RUTHERFORD_IIB_DATAHUB_URN,
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
                urn=RUTHERFORD_IIA_DATAHUB_URN,
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
