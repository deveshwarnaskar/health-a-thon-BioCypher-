"""Repository contracts (Gate 03).

Pure domain contracts. MUST NOT import SQLAlchemy, SQLite, PostgreSQL drivers,
Redis, FastAPI, filesystem implementations, or any ORM model. Persistence
implementations arrive with the infrastructure layer in later gates.
"""

from typing import Generic, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class Repository(Protocol, Generic[T]):
    def add(self, entity: T) -> None: ...
    def get_by_id(self, entity_id: object) -> T | None: ...
    def list(self) -> list[T]: ...
    def remove(self, entity: T) -> None: ...