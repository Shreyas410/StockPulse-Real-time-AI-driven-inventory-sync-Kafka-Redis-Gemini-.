import pytest
from httpx import AsyncClient

from app import app


@pytest.mark.asyncio
async def test_get_inventory_initial():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/inventory")
    assert r.status_code == 200
    data = r.json()
    assert "tshirts" in data and "pants" in data


@pytest.mark.asyncio
async def test_update_inventory_success():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Add 5 tshirts
        r = await ac.post("/inventory", json={"item": "tshirts", "change": 5})
        assert r.status_code == 200
        data = r.json()
        assert data["tshirts"] >= 25


@pytest.mark.asyncio
async def test_update_inventory_negative_result():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Try to remove too many pants
        r = await ac.post("/inventory", json={"item": "pants", "change": -999})
        assert r.status_code == 400

