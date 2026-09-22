from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import ROOT, get_settings

_url = get_settings().database_url
if _url.startswith("sqlite:///"):
    _raw_path = _url[len("sqlite:///"):]
    _p = Path(_raw_path)
    if not _p.is_absolute():
        if _p.name == "test.db":
            _url = f"sqlite:///{ROOT / 'backend' / 'test.db'}"
        else:
            _url = f"sqlite:///{ROOT / 'backend' / 'lifeline.db'}"

_sqlite = _url.startswith("sqlite")
engine = create_engine(_url, pool_pre_ping=True, **({"connect_args": {"check_same_thread": False, "timeout": 30}} if _sqlite else {}))
if _sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):  # WAL avoids writer/reader lock contention between API and pipeline threads
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
