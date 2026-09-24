"""SQLAlchemy Declarative Base (Gate 05).

All infrastructure persistence models inherit from this Base.
Domain entities MUST NOT inherit from Base.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarative class for infrastructure persistence models."""
    pass
