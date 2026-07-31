"""PostgreSQL adapter — write path (Pal → PG) and read path (PG → Pal)."""

from .adapter import PostgresWriter  # noqa: F401
from .loader import PostgresLoader  # noqa: F401
