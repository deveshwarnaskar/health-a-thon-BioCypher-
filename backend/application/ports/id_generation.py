"""Identifier generation port (Gate 04).

Use cases must not scatter ``uuid.uuid4()`` where deterministic testing
requires control. They ask this port. Infrastructure supplies a real generator
in a later gate; tests supply a deterministic one.
"""

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class IdGenerator(Protocol):
    def new_uuid(self) -> UUID: ...