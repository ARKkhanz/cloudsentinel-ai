import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Session-scoped FastAPI TestClient fixture.
    
    Provides an in-memory HTTP client that executes requests directly
    against the ASGI application stack without needing an active network socket.
    """
    with TestClient(app) as test_client:
        yield test_client
