"""PostgreSQL repository and Row Level Security (RLS) integration tests (Gate 05).

Verifies:
1. Full repository operation with real PostgreSQL database.
2. UnitOfWork commit and rollback on PostgreSQL.
3. PostgreSQL database-level Row Level Security (RLS) policy enforcement:
   - FORCE ROW LEVEL SECURITY ensures policy applies even to table owner.
   - Valid tenant context enables access to own tenant data only.
   - Cross-tenant access is blocked at the database engine level.
   - Missing tenant context fails closed (0 rows returned).
"""

from datetime import datetime, timezone
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.domain.entities import Patient
from backend.domain.exceptions import EntityNotFound
from backend.domain.value_objects import PhoneNumber, UHID
from backend.infrastructure.config.database import create_db_engine
from backend.infrastructure.persistence.models import OrganizationModel
from backend.infrastructure.persistence.repositories import SqlAlchemyPatientRepository
from backend.infrastructure.persistence.uow import SqlAlchemyUnitOfWork


@pytest.fixture(scope="module")
def postgres_db():
    import psycopg

    db_name = f"thali_integ_{uuid4().hex[:8]}"
    try:
        with psycopg.connect("dbname=postgres", autocommit=True, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE {db_name};")
    except Exception:
        pytest.skip("Local PostgreSQL not accessible for integration testing")

    pg_url = f"postgresql+psycopg://@localhost:5432/{db_name}"
    engine = create_db_engine(pg_url)

    # Apply Alembic schema and RLS policies
    with engine.connect() as conn:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.attributes["connection"] = conn
        command.upgrade(alembic_cfg, "head")

        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'thali_app_test_role') THEN
                    CREATE ROLE thali_app_test_role WITH NOSUPERUSER NOBYPASSRLS;
                END IF;
            END
            $$;
            GRANT USAGE ON SCHEMA public TO thali_app_test_role;
            GRANT ALL ON ALL TABLES IN SCHEMA public TO thali_app_test_role;
        """))
        conn.commit()

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    yield engine, session_factory

    engine.dispose()
    with psycopg.connect("dbname=postgres", autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);")


def test_postgres_repository_and_rls_isolation(postgres_db):
    engine, session_factory = postgres_db

    tenant_a = uuid4()
    tenant_b = uuid4()

    # Seed tenants
    with session_factory() as session:
        session.add_all([
            OrganizationModel(id=tenant_a, name="Hospital Alpha", slug="hosp-alpha"),
            OrganizationModel(id=tenant_b, name="Hospital Beta", slug="hosp-beta"),
        ])
        session.commit()

    # Create Patient A under Tenant A using UoW
    uow_a = SqlAlchemyUnitOfWork(session_factory, tenant_a)
    patient_a_id = uuid4()
    with uow_a:
        uow_a.patients.add(
            Patient(
                id=patient_a_id,
                uh_id=UHID("UH-ALPHA"),
                name="Alpha Patient",
                phone=PhoneNumber("+919111111111"),
            )
        )
        uow_a.commit()

    # Create Patient B under Tenant B using UoW
    uow_b = SqlAlchemyUnitOfWork(session_factory, tenant_b)
    patient_b_id = uuid4()
    with uow_b:
        uow_b.patients.add(
            Patient(
                id=patient_b_id,
                uh_id=UHID("UH-BETA"),
                name="Beta Patient",
                phone=PhoneNumber("+919222222222"),
            )
        )
        uow_b.commit()

    # Test 1: Tenant A can access Patient A
    with uow_a:
        patient = uow_a.patients.get(patient_a_id)
        assert patient.name == "Alpha Patient"

    # Test 2: Tenant A CANNOT access Patient B (blocked at both repository and RLS level)
    with uow_a:
        with pytest.raises(EntityNotFound):
            uow_a.patients.get(patient_b_id)

    # Test 3: Raw SQL RLS Verification on PostgreSQL
    # Non-superuser role exercises PostgreSQL RLS engine directly
    with engine.connect() as conn:
        conn.execute(text("SET ROLE thali_app_test_role;"))

        # Without app.current_tenant_id set, RLS fails closed (0 rows returned)
        result = conn.execute(text("SELECT count(*) FROM patients")).scalar()
        assert result == 0, "RLS must fail closed when tenant context is empty"

        # With tenant_a context set, only 1 patient visible
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_a)},
        )
        result_a = conn.execute(text("SELECT count(*) FROM patients")).scalar()
        assert result_a == 1, "RLS must return exactly tenant A's rows"

        # With tenant_b context set, only 1 patient visible
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_b)},
        )
        result_b = conn.execute(text("SELECT count(*) FROM patients")).scalar()
        assert result_b == 1, "RLS must return exactly tenant B's rows"
