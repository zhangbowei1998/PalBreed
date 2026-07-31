"""
pl_agent.core — canonical data models.

Public API:
  - Pal, WorkSuitability, BreedingRules  — data models
  - DataLoader                           — JSON fallback loading
  - errors                               — domain exceptions
"""

from pl_agent.core.schema import (
    BreedingRules,
    Element,
    Pal,
    SelfOnly,
    SpecialCombination,
    Unbreedable,
    WorkSuitability,
    WorkType,
)
from pl_agent.core.errors import (
    AdapterError,
    BreedingLoopError,
    DataIntegrityError,
    PalNotFoundError,
    ParseError,
    PlAgentError,
)
from pl_agent.core.data_loader import DataLoader

__all__ = [
    "Pal",
    "WorkSuitability",
    "BreedingRules",
    "Element",
    "WorkType",
    "SpecialCombination",
    "SelfOnly",
    "Unbreedable",
    "DataLoader",
    "PlAgentError",
    "PalNotFoundError",
    "BreedingLoopError",
    "DataIntegrityError",
    "ParseError",
    "AdapterError",
]
