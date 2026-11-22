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
    "clinical_handovers",
    "handover_acknowledgements",
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

        # 2. Upgrade to head (003_hospital_registry_lifecycle)
        command.upgrade(cfg, "head")
        engine2 = create_engine(db_url)
        insp2 = inspect(engine2)
        tables_head = set(insp2.get_table_names())
        assert EXPECTED_DOMAIN_TABLES.issubset(tables_head)
        h_cols = {c["name"] for c in insp2.get_columns("hospitals")}
        assert "status" in h_cols
        assert "hospital_type" in h_cols
        assert "contact_email" in h_cols
        cap_cols = {c["name"] for c in insp2.get_columns("hospital_capabilities")}
        assert "verification_notes" in cap_cols
        assert "verification_source" in cap_cols
        ref_cols = {c["name"] for c in insp2.get_columns("referral_requests")}
        assert "requested_resource_type" in ref_cols
        assert "idempotency_key" in ref_cols
        handover_cols = {c["name"] for c in insp2.get_columns("clinical_handovers")}
        assert "handover_data" in handover_cols
        assert "status" in handover_cols
        case_cols = {c["name"] for c in insp2.get_columns("emergency_cases")}
        assert "idempotency_key" in case_cols
        assert "current_handover_id" in case_cols
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
