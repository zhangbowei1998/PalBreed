"""Abstract interfaces for core engine components.

All engine implementations SHOULD implement these protocols
to allow swapping implementations in tests and future extensions.
"""

from __future__ import annotations

from typing import Protocol

from pl_agent.core.schema import BreedingRules, Pal


class PalDataSource(Protocol):
    """Protocol for any data source that provides Pal data."""

    def get_all(self) -> list[Pal]:
        """Return all Pals."""
        ...

    def get_by_id(self, pal_id: str) -> Pal | None:
        """Get a Pal by its unique ID."""
        ...

    def get_wild_pals(self) -> list[Pal]:
        """Return only wild-catchable Pals."""
        ...

    def get_sorted_by_rank(self) -> list[Pal]:
        """Return all Pals sorted by CombiRank."""
        ...


class SuitabilityQuerier(Protocol):
    """Protocol for work suitability queries."""

    def query(self, work_type: str, min_level: int) -> list[tuple[Pal, int]]:
        """Find Pals with a given work type and minimum level."""
        ...


class BreedingCalculator(Protocol):
    """Protocol for breeding calculations."""

    def forward(self, parent_a: Pal, parent_b: Pal) -> Pal:
        """Calculate child from two parents."""
        ...

    def reverse(self, child: Pal) -> list[tuple[Pal, Pal]]:
        """Find all possible parent pairs for a child."""
        ...


class BreedingTreeConstructor(Protocol):
    """Protocol for building breeding trees."""

    def build(self, target: Pal, max_depth: int = 5) -> object:
        """Build a breeding tree for the target Pal."""
        ...


class RuleProvider(Protocol):
    """Protocol for accessing breeding rules."""

    def get_rules(self) -> BreedingRules:
        """Return current breeding rules."""
        ...

    def is_special(self, parent_a: str, parent_b: str) -> str | None:
        """Check if a pair has a special combination. Returns child ID or None."""
        ...

    def is_self_only(self, pal_id: str) -> bool:
        """Check if a Pal can only breed with itself."""
        ...

    def is_unbreedable(self, pal_id: str) -> bool:
        """Check if a Pal cannot be obtained through breeding."""
        ...
