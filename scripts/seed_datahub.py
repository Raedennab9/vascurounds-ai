#!/usr/bin/env python3
"""Idempotently seed the four synthetic ALI datasets into DataHub."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from vascurounds.case_urns import (
    RUTHERFORD_I_DATAHUB_URN,
    RUTHERFORD_IIA_DATAHUB_URN,
    RUTHERFORD_IIB_DATAHUB_URN,
    RUTHERFORD_III_DATAHUB_URN,
)
from vascurounds.providers.factory import (
    DEFAULT_DATAHUB_GMS_URL,
    validate_datahub_gms_url,
)


@dataclass(frozen=True, slots=True)
class SeedCase:
    urn: str
    title: str
    rutherford_class: str
    description: str


SEED_CASES = (
    SeedCase(
        urn=RUTHERFORD_I_DATAHUB_URN,
        title="Rutherford I — Viable",
        rutherford_class="I",
        description=(
            "Synthetic acute limb ischemia case with preserved sensation and "
            "motor function and audible Doppler signals."
        ),
    ),
    SeedCase(
        urn=RUTHERFORD_IIA_DATAHUB_URN,
        title="Rutherford IIa — Marginally Threatened",
        rutherford_class="IIa",
        description=(
            "Synthetic acute limb ischemia case with mild sensory loss limited "
            "to the toes, no motor weakness, absent arterial Doppler signal, "
            "and preserved venous Doppler signal."
        ),
    ),
    SeedCase(
        urn=RUTHERFORD_IIB_DATAHUB_URN,
        title="Rutherford IIb — Immediately Threatened",
        rutherford_class="IIb",
        description=(
            "Synthetic acute limb ischemia case with sensory loss beyond the "
            "toes and mild-to-moderate motor weakness."
        ),
    ),
    SeedCase(
        urn=RUTHERFORD_III_DATAHUB_URN,
        title="Rutherford III — Irreversible",
        rutherford_class="III",
        description=(
            "Synthetic acute limb ischemia case with profound sensory and motor "
            "loss and absent arterial and venous Doppler signals."
        ),
    ),
)


def _datahub_types() -> tuple[type[Any], type[Any], type[Any]]:
    try:
        from datahub.emitter.mcp import MetadataChangeProposalWrapper
        from datahub.emitter.rest_emitter import DatahubRestEmitter
        from datahub.metadata.schema_classes import DatasetPropertiesClass
    except ImportError as exc:
        raise RuntimeError(
            "The DataHub Python package is required to seed metadata. "
            "Run this script in the Codespace where DataHub OSS is installed."
        ) from exc

    return (
        DatahubRestEmitter,
        MetadataChangeProposalWrapper,
        DatasetPropertiesClass,
    )


def seed_datahub(gms_url: str) -> int:
    """Upsert one dataset-properties aspect per canonical case URN."""

    validated_url = validate_datahub_gms_url(gms_url)
    emitter_type, proposal_type, properties_type = _datahub_types()
    emitter = emitter_type(gms_server=validated_url)
    try:
        emitter.test_connection()

        for case in SEED_CASES:
            properties = properties_type(
                name=case.title,
                description=case.description,
                customProperties={
                    "rutherford_class": case.rutherford_class,
                    "data_type": "Synthetic educational case",
                    "intended_use": "Professional education and simulation",
                    "contains_patient_data": "No",
                    "decision_support": "No",
                },
            )
            proposal = proposal_type(entityUrn=case.urn, aspect=properties)
            emitter.emit_mcp(proposal)
            print(f"Upserted {case.rutherford_class}: {case.urn}")
    finally:
        emitter.close()

    print(f"Seeded {len(SEED_CASES)} synthetic VascuRounds datasets.")
    return 0


def main() -> int:
    return seed_datahub(
        os.environ.get("DATAHUB_GMS_URL", DEFAULT_DATAHUB_GMS_URL)
    )


if __name__ == "__main__":
    raise SystemExit(main())
