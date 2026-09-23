import pytest
from fastapi.testclient import TestClient

from app.catalog import default_catalog
from app.main import create_app


@pytest.fixture(scope="session")
def catalog():
    return default_catalog()


@pytest.fixture()
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as test_client:
        yield test_client
