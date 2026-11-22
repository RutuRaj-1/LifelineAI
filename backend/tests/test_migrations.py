import os
import tempfile
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_BASE_TABLES = {
    "hospitals",
    "users",
    "patients",
    "doctors",
    "medical_reports",
    "hospital_resources",
    "emergency_cases",
    "notifications",
    "activity_logs",
    "alembic_version",
}

EXPECTED_DOMAIN_TABLES = EXPECTED_BASE_TABLES.union({
    "hospital_departments",
    "hospital_capabilities",
    "specialist_availabilities",
    "patient_clinical_facts",
    "clinical_provenance",
    "resource_status_history",
    "referral_requests",
    "referral_responses",
    "resource_reservations",
    "emergency_incident_reports",
})


def test_alembic_upgrade_and_downgrade_full_chain():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "migration_chain_test.db")
        db_url = f"sqlite:///{db_path}"

        # Initialize Alembic config targeting temporary database
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", db_url)

        # 1. Upgrade to 001_initial_schema baseline
        command.upgrade(cfg, "001_initial_schema")
        engine = create_engine(db_url)
        tables_001 = set(inspect(engine).get_table_names())
        assert EXPECTED_BASE_TABLES.issubset(tables_001)
        assert "hospital_departments" not in tables_001
        engine.dispose()

        # 2. Upgrade to head (002_domain_model_evolution)
        command.upgrade(cfg, "head")
        engine2 = create_engine(db_url)
        tables_head = set(inspect(engine2).get_table_names())
        assert EXPECTED_DOMAIN_TABLES.issubset(tables_head)
        engine2.dispose()

        # 3. Downgrade back to 001_initial_schema
        command.downgrade(cfg, "001_initial_schema")
        engine3 = create_engine(db_url)
        tables_reverted = set(inspect(engine3).get_table_names())
        assert "hospital_departments" not in tables_reverted
        assert "referral_requests" not in tables_reverted
        assert "patient_clinical_facts" not in tables_reverted
        assert EXPECTED_BASE_TABLES.issubset(tables_reverted)
        engine3.dispose()

        # 4. Downgrade to base
        command.downgrade(cfg, "base")
        engine4 = create_engine(db_url)
        tables_base = set(inspect(engine4).get_table_names())
        assert "hospitals" not in tables_base
        assert "users" not in tables_base
        engine4.dispose()

        # 5. Direct upgrade from base to head
        command.upgrade(cfg, "head")
        engine5 = create_engine(db_url)
        tables_final = set(inspect(engine5).get_table_names())
        assert EXPECTED_DOMAIN_TABLES.issubset(tables_final)
        engine5.dispose()
