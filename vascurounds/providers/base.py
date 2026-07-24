from __future__ import annotations

from typing import Protocol

from vascurounds.models import CaseAsset


class ProviderUnavailableError(RuntimeError):
    """Raised when a case provider cannot retrieve its catalog."""


class CaseProvider(Protocol):
    @property
    def fallback_active(self) -> bool:
        """Whether an offline fallback supplied the current result."""

    def list_cases(self) -> list[CaseAsset]:
        """Return the eligible synthetic educational cases."""
