from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def register_sqlite_search_helpers(connection, _record):
        connection.create_function(
            "app_casefold",
            1,
            lambda value: value.casefold() if isinstance(value, str) else value,
            deterministic=True,
        )
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
