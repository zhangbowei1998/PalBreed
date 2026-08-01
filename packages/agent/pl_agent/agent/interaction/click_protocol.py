"""Click protocol parser with fallback command support."""

from __future__ import annotations


def parse_expand_fallback(message: str) -> str | None:
    content = message.strip()
    if not content.startswith("/expand "):
        return None
    pal_id = content[len("/expand ") :].strip()
    return pal_id or None
