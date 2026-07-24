from __future__ import annotations

from typing import Any

from scripts import seed_datahub as seed_module
from vascurounds.case_urns import ACUTE_LIMB_ISCHEMIA_URNS


class FakeProperties:
    def __init__(self, **values: Any) -> None:
        self.values = values


class FakeProposal:
    def __init__(self, *, entityUrn: str, aspect: FakeProperties) -> None:
        self.entity_urn = entityUrn
        self.aspect = aspect


class FakeEmitter:
    instances: list["FakeEmitter"] = []

    def __init__(self, *, gms_server: str) -> None:
        self.gms_server = gms_server
        self.connected = False
        self.closed = False
        self.proposals: list[FakeProposal] = []
        self.__class__.instances.append(self)

    def test_connection(self) -> None:
        self.connected = True

    def emit_mcp(self, proposal: FakeProposal) -> None:
        self.proposals.append(proposal)

    def close(self) -> None:
        self.closed = True


def test_seed_cases_use_only_the_canonical_urn_collection() -> None:
    assert tuple(case.urn for case in seed_module.SEED_CASES) == (
        ACUTE_LIMB_ISCHEMIA_URNS
    )


def test_repeated_seeding_upserts_identical_safe_metadata(
    monkeypatch,
) -> None:
    FakeEmitter.instances.clear()
    monkeypatch.setattr(
        seed_module,
        "_datahub_types",
        lambda: (FakeEmitter, FakeProposal, FakeProperties),
    )

    assert seed_module.seed_datahub("http://localhost:8080") == 0
    assert seed_module.seed_datahub("http://localhost:8080") == 0

    assert len(FakeEmitter.instances) == 2
    first, second = FakeEmitter.instances
    assert first.connected and first.closed
    assert second.connected and second.closed
    assert [proposal.entity_urn for proposal in first.proposals] == list(
        ACUTE_LIMB_ISCHEMIA_URNS
    )
    assert [proposal.entity_urn for proposal in second.proposals] == [
        proposal.entity_urn for proposal in first.proposals
    ]

    for proposal in first.proposals:
        custom_properties = proposal.aspect.values["customProperties"]
        assert custom_properties == {
            "rutherford_class": next(
                case.rutherford_class
                for case in seed_module.SEED_CASES
                if case.urn == proposal.entity_urn
            ),
            "data_type": "Synthetic educational case",
            "intended_use": "Professional education and simulation",
            "contains_patient_data": "No",
            "decision_support": "No",
        }
