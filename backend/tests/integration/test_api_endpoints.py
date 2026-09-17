import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthz():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_categories_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/funds/v1/categories")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        codes = [c["code"] for c in data]
        assert "EQ_SMALL_CAP" in codes


@pytest.mark.asyncio
async def test_screener_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/screener/v1/screener")
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) > 0
        first = rows[0]
        assert "portfolio_id" in first
        assert "composite" in first
        assert "peer_pct_3m" in first


@pytest.mark.asyncio
async def test_net_return_calculator_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "initial_amount": 100000.0,
            "buy_nav": 100.0,
            "sell_nav": 120.0,
            "days_held": 180,
            "exit_load_rate": 0.01,
            "exit_load_days": 365,
            "stcg_rate": 0.20,
            "ltcg_rate": 0.125,
        }
        res = await ac.post("/api/analytics/v1/calculator/net-return", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["initial_investment"] == 100000.0
        assert data["exit_load"] == 1199.94
        assert data["net_profit"] > 0
