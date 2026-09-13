"""Infrastructure layer.

Technology adapters (PostgreSQL/SQLAlchemy/Alembic, Redis, Keycloak, S3,
WhatsApp, Gemini, reporting) implement ``application.ports`` and
``domain.repositories``. Nothing imports downward from here. External services
are NOT required at Gate 02B.
"""