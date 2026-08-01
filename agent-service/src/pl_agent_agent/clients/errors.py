"""Client-layer errors."""

from __future__ import annotations


class ClientError(Exception):
    pass


class UpstreamServiceError(ClientError):
    pass


class InvalidPayloadError(ClientError):
    pass


class PalNotFoundError(ClientError):
    pass
