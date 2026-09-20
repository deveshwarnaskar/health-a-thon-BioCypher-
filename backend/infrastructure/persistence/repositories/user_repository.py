"""SQLAlchemy repository for UserModel — used only by the auth layer."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.user_models import UserModel


class SqlAlchemyUserRepository:
    """Thin data-access object for user lookups during authentication.

    This repository intentionally bypasses the RLS unit-of-work because the
    login endpoint has no tenant context yet (the user is not authenticated).
    It uses a raw session with RLS disabled at the session level so the query
    can find the user across all tenants by email.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> UserModel | None:
        return (
            self._session.query(UserModel)
            .filter_by(email=email.lower().strip(), active=True)
            .first()
        )

    def get_by_id(self, user_id: UUID) -> UserModel | None:
        return (
            self._session.query(UserModel)
            .filter_by(id=user_id)
            .first()
        )

    def add(self, user: UserModel) -> UserModel:
        self._session.add(user)
        return user
