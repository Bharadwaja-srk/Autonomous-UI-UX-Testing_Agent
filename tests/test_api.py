"""
API endpoint tests for FastAPI backend.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test runs list
        resp = await ac.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data

        # Test start test validation (empty body)
        resp = await ac.post("/api/test", json={"url": "", "goal": ""})
        assert resp.status_code == 400

        # Test starting a valid test
        resp = await ac.post("/api/test", json={
            "url": "http://127.0.0.1:8000/demo/",
            "goal": "Test API launch",
            "max_steps": 2,
            "headless": True
        })
        assert resp.status_code == 200
        run_data = resp.json()
        assert "run_id" in run_data
        run_id = run_data["run_id"]

        # Test querying test run status
        resp = await ac.get(f"/api/test/{run_id}")
        assert resp.status_code == 200
        status_data = resp.json()
        assert status_data["run_id"] == run_id
