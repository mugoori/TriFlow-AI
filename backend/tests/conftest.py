"""
TriFlow AI - Test Configuration
================================
pytest fixtures and configuration for backend tests
"""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ANTHROPIC_API_KEY"] = "test-api-key"

from app.main import app
from app.database import get_db, Base


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Create an authenticated client with a test user."""
    # Register and login a test user
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@triflow.ai",
            "password": "TestPassword123!",
            "display_name": "Test User"
        }
    )

    if register_response.status_code == 200:
        token = register_response.json().get("access_token")
    else:
        # User might already exist, try login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@triflow.ai",
                "password": "TestPassword123!"
            }
        )
        token = login_response.json().get("access_token")

    if token:
        client.headers["Authorization"] = f"Bearer {token}"

    return client


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """Create an authenticated client with admin privileges."""
    # For testing, we'll create an admin user
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@triflow.ai",
            "password": "AdminPassword123!",
            "display_name": "Admin User",
            "role": "admin"
        }
    )

    if register_response.status_code == 200:
        token = register_response.json().get("access_token")
    else:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "admin@triflow.ai",
                "password": "AdminPassword123!"
            }
        )
        token = login_response.json().get("access_token")

    if token:
        client.headers["Authorization"] = f"Bearer {token}"

    return client


# Test data fixtures
@pytest.fixture
def sample_sensor_data():
    """Sample sensor data for testing."""
    return {
        "sensor_id": "TEMP-001",
        "sensor_type": "temperature",
        "value": 75.5,
        "unit": "°C",
        "location": "Line 1",
        "metadata": {"zone": "production"}
    }


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing."""
    return {
        "name": "Temperature Alert Workflow",
        "description": "Alert when temperature exceeds threshold",
        "trigger": {
            "type": "condition",
            "config": {
                "sensor_type": "temperature",
                "operator": ">=",
                "threshold": 80
            }
        },
        "nodes": [
            {
                "id": "node-1",
                "type": "condition",
                "config": {"condition": "temperature >= 80"}
            },
            {
                "id": "node-2",
                "type": "action",
                "config": {"action": "send_slack_notification"}
            }
        ],
        "is_active": True
    }


@pytest.fixture
def sample_ruleset_data():
    """Sample Rhai ruleset for testing."""
    return {
        "name": "Temperature Check Rule",
        "description": "Check temperature thresholds",
        "category": "safety",
        "script": """
// Temperature safety check
fn check_temperature(temp) {
    if temp >= 80 {
        return "critical";
    } else if temp >= 60 {
        return "warning";
    }
    return "normal";
}

let result = check_temperature(sensor_value);
result
""",
        "is_active": True
    }
