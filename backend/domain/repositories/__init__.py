"""Repository interfaces (Gate 02B placeholders).

Abstract collection boundaries for later infrastructure persistence adapters.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Repository(Protocol):
    def add(self, entity: object) -> None: ...
    def get(self, entity_id: object) -> object | None: ...