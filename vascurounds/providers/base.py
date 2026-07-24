from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vascurounds.models import CaseAsset


class ProviderUnavailableError(RuntimeError):
    """Raised when a case provider cannot retrieve its catalog."""


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    """Runtime state for the provider that actually supplied the case catalog."""

    provider_name: str
    datahub_connected: bool
    fallback_used: bool
    required_connection_failed: bool
    status_message: str
    endpoint: str | None = None


class CaseProvider(Protocol):
    @property
    def fallback_active(self) -> bool:
        """Whether an offline fallback supplied the current result."""

    @property
    def status(self) -> ProviderStatus:
        """Return the actual provider state after the latest retrieval attempt."""

    def list_cases(self) -> list[CaseAsset]:
        """Return the eligible synthetic educational cases."""
