import pytest
from httpx import AsyncClient, ASGITransport

from src.api.main import app



@pytest.mark.anyio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_register_and_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register a new user
        reg_response = await client.post(
            "/auth/register",
            json={
                "username": "testuser_ci",
                "email": "ci@example.com",
                "password": "securepass123",
            },
        )
        assert reg_response.status_code == 200, reg_response.text
        data = reg_response.json()
        assert "token" in data
        assert data["user"]["username"] == "testuser_ci"

        # Login with the same credentials
        login_response = await client.post(
            "/auth/login",
            json={"identifier": "testuser_ci", "password": "securepass123"},
        )
        assert login_response.status_code == 200
        assert "token" in login_response.json()


@pytest.mark.anyio
async def test_register_duplicate_returns_409():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "username": "duplicate_user",
            "email": "dup@example.com",
            "password": "securepass123",
        }
        await client.post("/auth/register", json=payload)
        response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.anyio
async def test_login_invalid_credentials():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/login",
            json={"identifier": "nobody", "password": "wrongpass"},
        )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_threads_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/threads")
    assert response.status_code == 401
