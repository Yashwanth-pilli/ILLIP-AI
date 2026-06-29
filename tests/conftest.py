"""Shared pytest fixtures and configuration."""

import pytest
import pytest_asyncio


# asyncio mode is set in pytest.ini — just re-export for clarity
@pytest.fixture(scope="session")
def test_client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        yield client
