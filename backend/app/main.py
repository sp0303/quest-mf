"""quest-mf: Unified Modular Monolith FastAPI Backend.

Provides all bounded contexts:
- /api/auth/v1
- /api/funds/v1
- /api/market/v1
- /api/analytics/v1
- /api/screener/v1
- /api/backtests/v1
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.backtests import router as backtests_router
from app.api.funds import router as funds_router
from app.api.market import router as market_router
from app.api.screener import router as screener_router
from app.config import settings
from app.core.cache import close_redis, get_redis
from app.core.db import close_pool, init_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("questmf.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up quest-mf unified API application...")
    await init_pool()
    await get_redis()
    yield
    logger.info("Shutting down quest-mf unified API application...")
    await close_pool()
    await close_redis()


app = FastAPI(
    title="quest-mf API",
    description="Quantitative Mutual Fund Research Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routers under /api
app.include_router(auth_router, prefix="/api")
app.include_router(funds_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(screener_router, prefix="/api")
app.include_router(backtests_router, prefix="/api")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "questmf-monolith"}


@app.get("/")
async def root():
    return {
        "name": "quest-mf API",
        "status": "online",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
