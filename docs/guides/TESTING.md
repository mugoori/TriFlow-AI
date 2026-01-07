# TriFlow AI - Testing Guide

## Overview

This guide covers running tests for the TriFlow AI backend.

## Prerequisites

```bash
cd backend
pip install -r requirements-test.txt
```

## Running Tests

### All Tests

**Linux/macOS:**
```bash
./scripts/run-tests.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\run-tests.ps1
```

### With Coverage

```bash
./scripts/run-tests.sh --cov
# or
.\scripts\run-tests.ps1 -Coverage
```

Coverage report: `backend/htmlcov/index.html`

### Quick Tests (Skip Slow/E2E)

```bash
./scripts/run-tests.sh --quick
```

### E2E Tests Only

```bash
./scripts/run-tests.sh --e2e
```

### Manual pytest

```bash
cd backend
python -m pytest tests/ -v

# Specific file
python -m pytest tests/test_auth.py -v

# Specific test
python -m pytest tests/test_auth.py::TestAuthEndpoints::test_login_success -v
```

## Test Structure

```
backend/tests/
├── conftest.py          # Fixtures & configuration
├── test_auth.py         # Authentication tests
├── test_sensors.py      # Sensor endpoint tests
├── test_workflows.py    # Workflow CRUD tests
├── test_rulesets.py     # Ruleset tests (admin)
├── test_chat.py         # Chat/AI agent tests
└── test_e2e_flows.py    # End-to-end user flows
```

## Test Categories

### Unit Tests
Test individual functions/methods in isolation.

```python
@pytest.mark.asyncio
async def test_health_check(self, client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
```

### Integration Tests
Test multiple components working together.

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_workflow_lifecycle(self, authenticated_client):
    # Create -> Update -> Execute -> Delete
    ...
```

### E2E Tests
Test complete user flows.

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_registration_flow(self, client):
    # Register -> Login -> Access protected resource
    ...
```

## Fixtures

### Available Fixtures

| Fixture | Description |
|---------|-------------|
| `client` | Unauthenticated HTTP client |
| `authenticated_client` | Client with test user token |
| `admin_client` | Client with admin privileges |
| `db_session` | Fresh database session |
| `sample_sensor_data` | Sample sensor payload |
| `sample_workflow_data` | Sample workflow payload |
| `sample_ruleset_data` | Sample ruleset payload |

### Using Fixtures

```python
@pytest.mark.asyncio
async def test_create_workflow(
    self,
    authenticated_client: AsyncClient,
    sample_workflow_data
):
    response = await authenticated_client.post(
        "/api/v1/workflows",
        json=sample_workflow_data
    )
    assert response.status_code in [200, 201]
```

## Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.slow` | Slow tests (skip with `--quick`) |
| `@pytest.mark.integration` | Integration tests |
| `@pytest.mark.e2e` | End-to-end tests |

### Using Markers

```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_large_data_processing(self, client):
    ...
```

Run specific markers:
```bash
pytest -m "slow"
pytest -m "not slow"
pytest -m "e2e or integration"
```

## Mocking

### Mock External Services

```python
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_chat_with_mock_ai(self, authenticated_client):
    with patch('app.services.ai_service.call_anthropic') as mock:
        mock.return_value = AsyncMock(return_value={
            "response": "Mocked AI response"
        })

        response = await authenticated_client.post(
            "/api/v1/chat",
            json={"message": "Hello"}
        )
        assert response.status_code == 200
```

### Mock Database

The `db_session` fixture automatically uses SQLite for testing:
```python
# conftest.py
TEST_DATABASE_URL = "sqlite:///./test.db"
```

## Best Practices

1. **Isolate Tests**: Each test should be independent
2. **Clean Up**: Use fixtures that reset state
3. **Descriptive Names**: `test_login_with_invalid_credentials_returns_401`
4. **Assert Specific**: Check exact values when possible
5. **Mark Slow Tests**: Use `@pytest.mark.slow` for tests > 1s

## Debugging Tests

### Verbose Output

```bash
pytest -vvv tests/test_auth.py
```

### Print Statements

```bash
pytest -s tests/test_auth.py
```

### Stop on First Failure

```bash
pytest -x tests/
```

### Show Locals on Failure

```bash
pytest -l tests/
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements-test.txt

      - name: Run tests
        run: |
          cd backend
          pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```
