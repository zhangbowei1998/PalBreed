"""PostgreSQL adapter — write path (Pal → PG) and read path (PG → BreedingIndex)."""

from .adapter import PostgresWriter  # noqa: F401
from .loader import PostgresLoader, BreedingIndex  # noqa: F401
