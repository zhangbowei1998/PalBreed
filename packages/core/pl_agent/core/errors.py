"""Domain-specific exceptions for the breeding engine."""

from __future__ import annotations


class PlAgentError(Exception):
    """Base exception for all pl-agent errors."""
    pass


class PalNotFoundError(PlAgentError):
    """Raised when a Pal ID is not found in the dataset."""

    def __init__(self, pal_id: str):
        super().__init__(f"Pal not found: {pal_id}")
        self.pal_id = pal_id


class BreedingLoopError(PlAgentError):
    """Raised when a circular breeding dependency is detected."""

    def __init__(self, pal_chain: list[str]):
        chain = " → ".join(pal_chain)
        super().__init__(f"Breeding loop detected: {chain}")
        self.chain = pal_chain


class DataIntegrityError(PlAgentError):
    """Raised when data fails validation checks."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class ParseError(PlAgentError):
    """Raised when a critical field cannot be parsed from HTML."""

    def __init__(self, pal_id: str, field: str):
        super().__init__(f"Failed to parse {field} for {pal_id}")
        self.pal_id = pal_id
        self.field = field


class AdapterError(PlAgentError):
    """Raised when an adapter encounters an unrecoverable error."""

    def __init__(self, source: str, message: str):
        super().__init__(f"[{source}] {message}")
        self.source = source
