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
        assert data["net_profit"] > 0


@pytest.mark.asyncio
async def test_fund_summary_and_risk_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Summary
        res_sum = await ac.get("/api/analytics/v1/funds/101/summary")
        assert res_sum.status_code == 200
        data_sum = res_sum.json()
        assert data_sum["portfolio_id"] == 101
        assert "composite" in data_sum

        # Risk (Rule 1: precomputed)
        res_risk = await ac.get("/api/analytics/v1/funds/101/risk")
        assert res_risk.status_code == 200
        data_risk = res_risk.json()
        assert data_risk["portfolio_id"] == 101
        assert "volatility_ann" in data_risk
        assert "sharpe_ratio" in data_risk


@pytest.mark.asyncio
async def test_screener_matrix_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/screener/v1/matrix")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        first = data[0]
        assert "peer_pct_3m" in first
        assert "shp_3m" in first
        assert "quadrant" in first


@pytest.mark.asyncio
async def test_backtest_run_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "model_version": "v1_baseline",
            "top_k": 3,
            "rebalance_months": 3,
            "exec_lag_days": 1,
        }
        res_post = await ac.post("/api/backtests/v1/runs", json=payload)
        assert res_post.status_code == 200
        run_data = res_post.json()
        run_id = run_data["run_id"]
        assert run_id > 0
        assert run_data["status"] == "DONE"
        assert "cagr_gross" in run_data["summary"]
        assert "cagr_net" in run_data["summary"]

        # Get run
        res_get = await ac.get(f"/api/backtests/v1/runs/{run_id}")
        assert res_get.status_code == 200

        # Get series
        res_series = await ac.get(f"/api/backtests/v1/runs/{run_id}/series")
        assert res_series.status_code == 200
        series_data = res_series.json()
        assert len(series_data["gross"]) > 0
        assert len(series_data["net"]) > 0


@pytest.mark.asyncio
async def test_fund_profile_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/funds/v1/funds/101/profile")
        assert res.status_code == 200
        data = res.json()
        if data is not None:
            assert data["portfolio_id"] == 101
            assert "fund_manager" in data
            assert "riskometer" in data


@pytest.mark.asyncio
async def test_fund_holdings_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/funds/v1/funds/101/holdings")
        assert res.status_code == 200
        data = res.json()
        if data is not None:
            assert data["portfolio_id"] == 101
            assert "top_10_concentration_pct" in data
            assert "sector_allocation" in data
            assert isinstance(data["holdings"], list)


@pytest.mark.asyncio
async def test_fund_overlap_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/funds/v1/funds/101/overlap?compare_with=103")
        assert res.status_code == 200
        data = res.json()
        assert data["portfolio_a_id"] == 101
        assert data["portfolio_b_id"] == 103
        assert "overlap_pct" in data
        assert "common_holdings_count" in data
        assert isinstance(data["common_holdings"], list)
