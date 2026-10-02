import os
from pathlib import Path
import tempfile

_test_database_directory = tempfile.TemporaryDirectory(prefix="ai-caller-tests-")
_test_database_path = Path(_test_database_directory.name) / "test_ai_caller.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_database_path.as_posix()}"
os.environ["LLM_PROVIDER"]="mock"
os.environ["TELEPHONY_PROVIDER"]="mock"
os.environ["AUTH_MODE"]="local"
import pytest
from app.db.base import Base
from app.db.session import engine, SessionLocal

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield

@pytest.fixture
def db():
    s=SessionLocal(); yield s; s.close()
