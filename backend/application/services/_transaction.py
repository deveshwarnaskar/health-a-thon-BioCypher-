"""Shared transaction wrapper (Gate 04).

Guarantees that a use case commits exactly once on success and rolls back
without leaving partial state on any failure. Application use cases never
commit piecemeal.
"""

from typing import Callable, TypeVar

from ..ports.unit_of_work import UnitOfWork

T = TypeVar("T")


def in_transaction(uow: UnitOfWork, body: Callable[[], T]) -> T:
    try:
        result = body()
    except Exception:
        uow.rollback()
        raise
    uow.commit()
    return result