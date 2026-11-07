"""Every test gets a fresh isolated synthetic database; never write local demo data."""
import os
from pathlib import Path
import pytest

TEST_DB = Path(__file__).parent / "test_copilot.sqlite"
os.environ["APP_DATABASE_URL"] = "sqlite:///" + str(TEST_DB)
os.environ["APP_APPROVAL_TOKEN"] = "tests-only-token"
os.environ.pop("OPENAI_API_KEY", None)


@pytest.fixture(autouse=True)
def isolate_database():
    from app.database import engine
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)
    yield
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)
