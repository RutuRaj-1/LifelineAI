import os
import tempfile
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
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


def test_alembic_upgrade_and_downgrade():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "migration_test.db")
        db_url = f"sqlite:///{db_path}"

        # Initialize Alembic config targeting temporary database
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", db_url)

        # 1. Upgrade to head
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(tables), f"Missing tables: {EXPECTED_TABLES - tables}"

        # 2. Downgrade to base
        command.downgrade(cfg, "base")
        engine.dispose()

        engine2 = create_engine(db_url)
        tables_after_downgrade = set(inspect(engine2).get_table_names())
        assert "hospitals" not in tables_after_downgrade
        assert "users" not in tables_after_downgrade
        assert "patients" not in tables_after_downgrade
        engine2.dispose()

        # 3. Re-upgrade to head
        command.upgrade(cfg, "head")
        engine3 = create_engine(db_url)
        tables_re_upgraded = set(inspect(engine3).get_table_names())
        assert EXPECTED_TABLES.issubset(tables_re_upgraded)
        engine3.dispose()
