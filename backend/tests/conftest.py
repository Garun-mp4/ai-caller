import os
os.environ["DATABASE_URL"]="sqlite:///./test_ai_caller.db"
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
