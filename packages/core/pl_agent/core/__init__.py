"""
pl_agent.core — 配种引擎核心包

Public API:
  - Pal, WorkSuitability, BreedingRules  — canonical data models
  - DataLoader                           — data loading
  - BreedingEngine                       — forward/reverse breed calc
  - BreedingTreeBuilder                  — tree construction
  - SuitabilityQuery                     — work type queries
  - PathOptimizer                        — multi-path ranking
  - errors                               — domain exceptions
"""

from pl_agent.core.schema import (
    BreedingRules,
    DatasetMeta,
    Element,
    MutationRule,
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
from pl_agent.core.breeding_engine import BreedingEngine
from pl_agent.core.breeding_tree import (
    BreedingPath,
    BreedingStep,
    BreedingTree,
    BreedingTreeBuilder,
)
from pl_agent.core.suitability_query import LevelStats, SuitabilityQuery
from pl_agent.core.path_optimizer import PathOptimizer

__all__ = [
    # schema
    "Pal",
    "WorkSuitability",
    "BreedingRules",
    "DatasetMeta",
    "Element",
    "WorkType",
    "SpecialCombination",
    "SelfOnly",
    "Unbreedable",
    "MutationRule",
    # errors
    "PlAgentError",
    "PalNotFoundError",
    "BreedingLoopError",
    "DataIntegrityError",
    "ParseError",
    "AdapterError",
    # data
    "DataLoader",
    # engine
    "BreedingEngine",
    "BreedingTreeBuilder",
    "BreedingTree",
    "BreedingPath",
    "BreedingStep",
    "SuitabilityQuery",
    "LevelStats",
    "PathOptimizer",
]
