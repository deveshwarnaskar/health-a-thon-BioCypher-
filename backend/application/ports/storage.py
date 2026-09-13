"""Object storage port (Gate 02B).

Future implementation target: ``backend.infrastructure.storage`` (S3-compatible
object storage for report PDFs and chart artifacts).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IObjectStorage(Protocol):
    def put(self, key: str, payload: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...