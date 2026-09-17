# quest-mf — Low-Level Design: Backend (Python)

**Runtime:** Python 3.12 · FastAPI · uvicorn[standard] (uvloop + httptools) · asyncpg · redis-py (asyncio) · orjson · Pydantic v2 · Polars · DuckDB · NumPy / Numba
**Env:** a single `backend/.venv` for local dev; per-service Docker images in deployment.
**Parent:** [HLD](HLD.md) · DB: [LLD-database](LLD-database.md)

---

## 1. Monorepo layout (backend)

```text
backend/
├── .venv/                          # git-ignored
├── requirements/
│   ├── base.txt                    # shared runtime pins
│   ├── api.txt                     # -r base.txt + fastapi, uvicorn …
│   ├── worker.txt                  # -r base.txt + polars, duckdb, numba …
│   └── dev.txt                     # -r api.txt -r worker.txt + pytest, ruff, mypy …
├── pyproject.toml                  # ruff, mypy, pytest config (tooling only)
├── libs/
│   ├── common/                     # package: questmf_common
│   │   └── questmf_common/
│   │       ├── config.py           # BaseSettings per service
│   │       ├── db.py               # asyncpg pool factory, ro/rw
│   │       ├── cache.py            # versioned cache helpers
│   │       ├── events.py           # Redis Streams publisher/consumer
│   │       ├── auth.py             # JWT verify dependency, roles
│   │       ├── http.py             # ORJSONResponse, ETag, error model
│   │       ├── logging.py          # structlog JSON
│   │       ├── telemetry.py        # OTel + Prometheus
│   │       ├── health.py           # /healthz /readyz router
│   │       └── contracts/          # Pydantic event + DTO schemas shared by services
│   └── quant/                      # package: questmf_quant  (PURE — no I/O)
│       └── questmf_quant/
│           ├── calendar/windows.py         # CAL_/OBS_ resolution, boundary rule
│           ├── returns.py                  # simple/log/CAGR/XIRR
│           ├── rolling.py                  # vectorised rolling engine
│           ├── drawdown.py                 # numba kernels
│           ├── risk.py                     # vol, downside, beta, TE, IR, capture
│           ├── distribution.py             # point-in-time expanding stats
│           ├── percentile.py               # mid-rank, peer pct, SHP, shrinkage
│           ├── technical.py                # RSI, SMA, ROC, accel, rs_slope
│           ├── scoring.py                  # normalise + composite (model config)
│           ├── friction.py                 # load, stamp, STT, tax
│           ├── backtest/                   # walkforward.py, execution.py, stats.py
│           └── downsample.py               # LTTB
├── services/
│   ├── auth_service/
│   ├── fund_service/
│   ├── market_data_service/
│   ├── analytics_service/
│   ├── screener_service/
│   └── backtest_service/
├── workers/
│   ├── ingestion_worker/
│   ├── compute_worker/
│   ├── backtest_worker/
│   └── scheduler/
├── migrations/                     # Alembic (env.py, versions/)
└── tests/
    ├── unit/                       # quant lib (fast, no I/O)
    ├── property/                   # hypothesis
    ├── golden/                     # hand-verified fixtures
    ├── integration/                # testcontainers: PG+Timescale, Redis
    └── contract/                   # OpenAPI snapshot tests per service
```

### 1.1 Service internal layout (identical for every API service)

```text
services/screener_service/
├── Dockerfile
├── requirements.txt              # -r ../../requirements/api.txt (+ extras)
└── screener_service/
    ├── main.py                   # app factory, lifespan (pools), routers
    ├── settings.py               # class Settings(ServiceSettings)
    ├── api/
    │   ├── deps.py               # DI: get_repo, get_cache, current_user
    │   └── v1/
    │       ├── screener.py       # router — thin: parse → service → respond
    │       └── matrix.py
    ├── services/                 # business orchestration (cache-aside, shaping)
    │   └── screener.py
    ├── repositories/             # SQL only, returns tuples/records
    │   └── snapshot_repo.py
    ├── schemas/                  # Pydantic request/response models
    │   └── screener.py
    └── sql/                      # .sql files loaded at startup (named queries)
        └── screener_page.sql
```

**Layer rules:**

`router → service → repository → DB`. Routers never touch SQL. Repositories never touch HTTP or cache. Services contain no framework imports except type hints. The quant lib is called only from workers (and the calculator in analytics).

**File size limits:** ≤ 300 lines per module and ≤ 50 lines per function (ruff `C901` / `PLR0915` enforced).

## 2. Environment setup (venv)

**Windows (PowerShell):**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements/dev.txt
pip install -e libs/common -e libs/quant
```

**Linux / macOS:**

```bash
cd backend && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt && pip install -e libs/common -e libs/quant
```

Run one service locally:

```bash
uvicorn screener_service.main:app --app-dir services/screener_service --port 8005 --reload
```

## 3. Shared library design (`questmf_common`)

### 3.1 Settings

```python
class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QMF_", env_file=".env", extra="ignore")
    service_name: str
    port: int
    pg_dsn_ro: PostgresDsn
    pg_dsn_rw: PostgresDsn | None = None
    pg_pool_min: int = 2
    pg_pool_max: int = 20
    pg_statement_timeout_ms: int = 2000
    redis_url: RedisDsn
    redis_stream_url: RedisDsn
    jwt_public_key: str
    cors_origins: list[str] = []
    otel_endpoint: str | None = None
```

### 3.2 DB pool

```python
async def create_pool(dsn: str, *, min_size: int, max_size: int, timeout_ms: int) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn, min_size=min_size, max_size=max_size,
        command_timeout=timeout_ms / 1000,
        server_settings={"statement_timeout": str(timeout_ms), "jit": "off",
                         "application_name": settings.service_name},
        init=_register_codecs,          # orjson codec for jsonb, date codecs
    )
```

Pools are created in the FastAPI `lifespan` and stored on `app.state`. There are no global singletons at import time.

### 3.3 Versioned cache-aside

```python
async def cached_bytes(r: Redis, ns: str, key_parts: tuple, ttl: int,
                       loader: Callable[[], Awaitable[bytes]]) -> bytes:
    ver = await r.get(f"ver:{ns}") or b"0"
    key = f"{ns}:{ver.decode()}:{sha1(orjson.dumps(key_parts)).hexdigest()}"
    if (hit := await r.get(key)) is not None:
        return hit
    lock = r.lock(f"lk:{key}", timeout=5, blocking_timeout=2)   # stampede guard
    async with lock:
        if (hit := await r.get(key)) is not None:
            return hit
        data = await loader()
        await r.set(key, data, ex=ttl)
        return data
```

The response is `Response(content=bytes, media_type="application/json", headers={"ETag": etag})`. There is no re-serialisation on a hit.

If Redis is unavailable, the helper logs it, increments `cache_errors_total`, and **falls through to the loader**. The read path degrades; it does not fail.

### 3.4 Events (Redis Streams)

```python
class Event(BaseModel):
    event_id: UUID
    type: str                     # 'nav.ingested'
    occurred_at: datetime
    producer: str
    payload: dict
    schema_version: int = 1

class Publisher:
    async def publish(self, stream: str, evt: Event) -> str:
        return await self.r.xadd(stream, {"e": evt.model_dump_json()},
                                 maxlen=100_000, approximate=True)

class Consumer:
    # XREADGROUP loop; ack after handler success; retry count via XPENDING;
    # after 5 deliveries → XADD {stream}.dlq and XACK.
```

Handlers **must be idempotent**. They dedupe on `event_id` via `SET evt:{id} 1 NX EX 86400`.

### 3.5 Event catalogue

| Stream | Producer | Consumers | Payload |
|---|---|---|---|
| `jobs.ingest` | scheduler | ingestion-worker | `{business_date, sources[]}` |
| `jobs.compute` | scheduler / ops | compute-worker | `{as_of_date, mode: INCREMENTAL\|FULL, portfolio_shard}` |
| `nav.ingested` | ingestion-worker | compute-worker | `{business_date, ingest_ids[], changed_portfolios[]}` |
| `features.computed` | compute-worker | compute-worker (scoring stage) | `{as_of_date, snapshot_id}` |
| `scores.published` | compute-worker | all read services (cache warm) | `{as_of_date, snapshot_id, model_versions[]}` |
| `backtest.requested` | backtest-service | backtest-worker | `{run_id}` |
| `backtest.progress` | backtest-worker | backtest-service (SSE) | `{run_id, pct, stage}` |
| `backtest.completed` | backtest-worker | backtest-service | `{run_id, status, summary}` |

### 3.6 Auth dependency

```python
def require_role(*roles: Role):
    async def dep(token: str = Depends(bearer)) -> Principal:
        claims = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"],
                            audience="questmf", options={"require": ["exp", "sub", "role"]})
        if claims["role"] not in roles: raise HTTPException(403)
        return Principal(user_id=claims["sub"], role=claims["role"])
    return dep
```

Verification is local; there is no call to auth-service per request.

### 3.7 Error model (all services)

```json
{ "error": { "code": "FUND_NOT_FOUND", "message": "…", "request_id": "…", "details": {} } }
```

HTTP mapping: 400 validation, 401 unauthenticated, 403 forbidden, 404 not found, 409 conflict, 422 unprocessable, 429 rate-limited, 503 dependency down (with `Retry-After`).

## 4. API services

All routes are prefixed `/api/<service>/v1`. Nginx strips nothing, and each service mounts its own prefix. OpenAPI is served at `/api/<service>/v1/openapi.json` and aggregated in CI for frontend type generation.

Common query parameter: `as_of` (date, default = `scoring.latest`). Common headers: `If-None-Match`; `X-Request-ID` is echoed back.

### 4.1 auth-service :8001

| Method | Path | Body / Query | Response |
|---|---|---|---|
| POST | `/api/auth/v1/login` | `{email, password}` | `{access_token, expires_in}` + `Set-Cookie: rt` (httpOnly, Secure, SameSite=Strict) |
| POST | `/api/auth/v1/refresh` | cookie | `{access_token}` (rotates the refresh token) |
| POST | `/api/auth/v1/logout` | cookie | 204 |
| GET | `/api/auth/v1/me` | — | `{user_id, email, role}` |
| GET | `/api/auth/v1/.well-known/jwks.json` | — | JWKS |
| POST | `/api/auth/v1/users` | admin | create user |

Password hashing uses argon2id. Login is rate-limited to 5 attempts per minute per IP and per email, and the lockout is audited.

### 4.2 fund-service :8002

| Method | Path | Notes |
|---|---|---|
| GET | `/api/funds/v1/funds?q=&category=&amc=&cursor=&limit=50` | keyset pagination on `(display_name, portfolio_id)` |
| GET | `/api/funds/v1/search?q=` | trigram, top 10, cached 1 h |
| GET | `/api/funds/v1/funds/{portfolio_id}` | profile + share classes + current category/benchmark |
| GET | `/api/funds/v1/funds/{portfolio_id}/events` | timeline |
| GET | `/api/funds/v1/funds/{portfolio_id}/costs?as_of=` | TER history, current load rule |
| GET | `/api/funds/v1/categories` | cached 24 h |
| GET | `/api/funds/v1/amcs` | cached 24 h |

### 4.3 market-data-service :8003

| Method | Path | Notes |
|---|---|---|
| GET | `/api/market/v1/nav/{portfolio_id}?from=&to=&points=2000` | canonical series; LTTB when above `points`; uses `nav_monthly` when the range is more than 10 years and `points` < 600 |
| GET | `/api/market/v1/nav/{portfolio_id}/overlay?benchmark=&sma=20,50,200` | NAV + benchmark rebased to 100 + SMAs, one response |
| GET | `/api/market/v1/benchmarks/{benchmark_id}?from=&to=&points=` | |
| GET | `/api/market/v1/freshness` | last NAV date per source, DQ issue count |

Series response format (columnar):

```json
{ "portfolio_id": 101, "as_of": "2026-09-16", "downsampled": true,
  "t": ["2016-01-01", "..."], "series": { "nav": [12.1, "..."], "bench": [100, "..."] } }
```

### 4.4 analytics-service :8004

| Method | Path | Notes |
|---|---|---|
| GET | `/api/analytics/v1/funds/{id}/summary` | `analytics.fund_summary.payload` (a single row) |
| GET | `/api/analytics/v1/funds/{id}/rolling?window=CAL_3M&fields=ret,active_ret,max_dd&from=&points=` | columnar |
| GET | `/api/analytics/v1/funds/{id}/distribution?window=CAL_3M&variant=EXPANDING` | + histogram bins (precomputed from the stored series, cached) |
| GET | `/api/analytics/v1/funds/{id}/risk?horizon=3Y` | Sharpe, Sortino, beta, TE, IR, capture, MDD, recovery |
| GET | `/api/analytics/v1/funds/{id}/sip?window=CAL_3Y` | rolling SIP-XIRR distribution |
| POST | `/api/analytics/v1/calculator/net-return` | `{portfolio_id, amount, buy_date, sell_date, investor_profile}` → breakdown; pure function over `ref.load_rules` + `ref.tax_rules` |

### 4.5 screener-service :8005

| Method | Path | Notes |
|---|---|---|
| GET | `/api/screener/v1/screener` | `category, window, model, min_confidence, investable_only, max_ter, max_exit_load_days, sort, dir, limit ≤ 500` |
| GET | `/api/screener/v1/matrix?category=&model=` | points for the 2×2 chart: `{portfolio_id, peer_pct_3m, shp_3m, quadrant}` |
| GET | `/api/screener/v1/models` | model versions + weights |
| GET | `/api/screener/v1/latest` | `{model_version, as_of_date, published_at}` |

Allowed `sort` columns are a **whitelist enum** mapped to SQL column names, so there is no SQL injection path. Any sort other than `composite` still uses a partition-local sort of ≤ 300 rows (a category contains at most ~40–150 funds), which is fast.

Response (columnar):

```json
{ "as_of": "2026-09-16", "model": "v1_baseline", "category": "EQ_SMALL_CAP",
  "columns": ["portfolio_id","fund_name","ret_1m","ret_3m","ret_1y","shp_3m","peer_pct_3m",
              "alpha_3m","mdd_3y","ter","composite","confidence","flags","investable"],
  "rows": [[101,"Fund A",0.07,0.20,0.11,91,96,0.07,-0.08,0.0062,82.4,2,0,true]] }
```

### 4.6 backtest-service :8006

| Method | Path | Notes |
|---|---|---|
| POST | `/api/backtests/v1/runs` | analyst+; `Idempotency-Key` header; validates the config against a JSON Schema; → 202 |
| GET | `/api/backtests/v1/runs?cursor=` | list |
| GET | `/api/backtests/v1/runs/{id}` | status + summary |
| GET | `/api/backtests/v1/runs/{id}/series?names=EQUITY_NET,IC_3M` | columnar |
| GET | `/api/backtests/v1/runs/{id}/holdings?date=` | from partition, or the Parquet archive |
| GET | `/api/backtests/v1/runs/{id}/events` | **SSE** (`text/event-stream`), heartbeat every 15 s |
| POST | `/api/backtests/v1/runs/{id}/cancel` | sets the cancel flag in Redis; the worker checks it between dates |

Concurrency: at most 2 running backtests per user and 4 globally (worker consumer count).

## 5. Workers

### 5.1 scheduler :8104
- APScheduler (AsyncIO) with a **Redis leader lock** (`lock:scheduler`) so that only one instance fires.
- Jobs (IST):

| Job | Cron | Emits |
|---|---|---|
| Nightly NAV | `30 23 * * 1-6` | `jobs.ingest {sources:[AMFI_NAV]}` |
| Morning retry | `0 7 * * *` | same, if yesterday is missing |
| TRI + RF | `0 22 * * 1-5` | `jobs.ingest {sources:[NSE_TRI,RBI_TBILL]}` |
| TER / AUM monthly | `0 6 12 * *` | `jobs.ingest {sources:[AMFI_TER,AMFI_AUM]}` |
| Weekly full rebuild | `0 2 * * 0` | `jobs.compute {mode:FULL}` |
| Weekly reconciliation | `0 4 * * 0` | `jobs.ingest {sources:[MFAPI_RECON]}` |
| Backtest archive | `0 3 * * *` | internal |

### 5.2 ingestion-worker :8101

Pipeline per source: `Fetcher → RawStore → Parser → Validator → Loader → Publisher`

```python
class SourceAdapter(Protocol):
    name: str
    parser_version: str
    async def fetch(self, ctx: JobCtx) -> list[RawPayload]: ...     # httpx, retries, rate limit
    def parse(self, raw: RawPayload) -> pl.DataFrame: ...          # pure
    schema: pa.DataFrameSchema                                     # pandera
    target: LoadTarget                                             # staging table + merge SQL
```

Adapters: `AmfiNavDaily`, `AmfiNavHistory` (chunked ranges, resumable cursor stored in `ops`), `AmfiTer`, `AmfiAum`, `NseTri`, `RbiTbill`, `MfapiNav` (fallback + reconciliation), `SchemeMasterSync`.

- HTTP client: `httpx.AsyncClient(http2=True, timeout=30)`, a token-bucket limit per host (default 1 req/s), exponential backoff with jitter (max 5), and a circuit breaker that opens after 5 consecutive failures.
- Raw payloads are stored in `oci://questmf-raw/{source}/{yyyy}/{mm}/{dd}/{sha256}.gz` **before** parsing.
- Validation: `BLOCK` issues reject the row into `ops.dq_issues`; `WARN` issues are loaded and flagged.
- Load: `copy_records_to_table` → staging → merge SQL (LLD-database §4.3).
- Publishes `nav.ingested` with `changed_portfolios` so that compute only touches what changed.

### 5.3 compute-worker :8102

**Sharding:** the job is split into `S` shards by `portfolio_id % S`. Each shard is a separate stream message, consumed by any of the `N` worker processes (consumer group). Default `S = 16`, `N = 4` processes × 4 threads (Polars).

Stages (per shard, per `as_of_date`):

```text
1. load      : NAV (canonical scheme) + benchmark + RF  → Polars LazyFrames
               (PG `COPY (SELECT …) TO STDOUT (FORMAT binary)` or the Parquet lake)
2. rolling   : questmf_quant.rolling for all window_ids   (only end_dates > last computed, INCREMENTAL)
3. risk      : vol / downside / beta / TE / MDD kernels (numba)
4. distrib   : expanding distributions as of each new date (point-in-time)
5. write     : COPY → analytics.rolling_metrics / rolling_distribution / daily_features
```

After all shards ack (tracked in `ops` via a job manifest), the **cross-sectional stage** runs once:

```text
6. peer pct  : per date, per category (point-in-time categories), one row per portfolio
7. scoring   : for each active model_version → scoring.scores
8. snapshot  : build scoring.screener_snapshot for as_of (CREATE partition if needed; INSERT … SELECT)
               build analytics.fund_summary payloads
9. publish   : UPDATE scoring.latest · INCR ver:scores ver:analytics · XADD scores.published
10. warm     : request the top N query shapes (read services also warm on the event)
```

Correctness guards:
- The whole cross-sectional stage runs inside **one transaction** per `as_of`, so readers see either the old or the new snapshot.
- `snapshot_id` is set to `BUILDING` → `PUBLISHED` only after step 9.
- Point-in-time: every lookup of categories, benchmarks, loads or TER uses `valid @> as_of_date`.

Performance targets: incremental (1 new day) ≤ 15 min; full rebuild ≤ 3 h on 16 vCPU.

### 5.4 backtest-worker :8103

```text
consume backtest.requested
→ load config (JSON-Schema validated) + model
→ create partition backtest.results_r{run_id}
→ for d in schedule:
      universe = eligible & investable as of d          (point-in-time)
      scores   = scoring.scores @ d  (or recompute if the config overrides weights)
      picks    = select(scores, rule)
      fills    = execution.apply(picks, lag=EXEC_LAG, switch_gap, min_hold)
      fwd      = forward returns (gross, net-load, net-tax) from NAV
      buffer rows; every 50k → COPY
      publish progress every 2 %; check the cancel flag
→ stats: IC per date, HAC t-stat, block bootstrap CI, quintile spread, turnover, CAGR/Sharpe/MDD
→ write run_series + runs.summary → status DONE → backtest.completed
```

The heavy math lives in `questmf_quant.backtest` (pure and unit-tested). The worker is only I/O and orchestration.

## 6. Performance engineering checklist (backend)

- [ ] `uvicorn --loop uvloop --http httptools --workers $(nproc)`, or gunicorn with `uvicorn.workers.UvicornWorker`
- [ ] `default_response_class=ORJSONResponse`; hot paths return pre-built `bytes`
- [ ] No `SELECT *` in services; explicit columns matching covering indexes
- [ ] Named SQL loaded once; asyncpg prepared statements (PgBouncer ≥ 1.21 `max_prepared_statements`)
- [ ] `statement_timeout` 2 s on the read pool; 0 on worker pools, but with `idle_in_transaction_session_timeout`
- [ ] Redis socket timeout 50 ms; cache failures fall through
- [ ] GZip is **not** done in Python (Nginx brotli handles it)
- [ ] Middleware kept minimal: request-id, timing, OTel; no body logging
- [ ] Load test (k6) in CI on staging: 500 RPS screener at p95 < 80 ms
- [ ] `py-spy` profiles attached to any PR that touches a hot path

## 7. Testing

| Level | Tooling | Scope | Gate |
|---|---|---|---|
| Unit | pytest | `questmf_quant` (all spec v2 §28 tests A–S live here) | ≥ 90 % coverage on quant |
| Property | hypothesis | window math, leakage (SHP unchanged by appending future data) | required |
| Golden | pytest + CSV fixtures | hand-computed spreadsheets | exact to 1e-9 |
| Integration | testcontainers (timescale/timescaledb-ha, redis) | repositories, merge SQL, streams, EXPLAIN checks | required |
| Contract | schemathesis + OpenAPI snapshot | every API service | required |
| Load | k6 | read services on staging | nightly |
| Lint / type | ruff, mypy `--strict` on libs | all | required |

## 8. Dockerfile template (API service)

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS deps
COPY requirements/ requirements/
COPY services/screener_service/requirements.txt svc-req.txt
RUN python -m venv /venv && /venv/bin/pip install -r svc-req.txt

FROM base AS runtime
RUN useradd -r -u 10001 app
COPY --from=deps /venv /venv
COPY libs/ libs/
RUN /venv/bin/pip install --no-deps libs/common
COPY services/screener_service/screener_service screener_service
USER app
ENV PATH="/venv/bin:$PATH"
EXPOSE 8005
HEALTHCHECK CMD python -c "import urllib.request,sys;urllib.request.urlopen('http://127.0.0.1:8005/healthz')" || exit 1
CMD ["uvicorn","screener_service.main:app","--host","0.0.0.0","--port","8005",
     "--loop","uvloop","--http","httptools","--workers","4","--proxy-headers"]
```

Worker images install `requirements/worker.txt` and `libs/quant`. Images are built for **linux/arm64 and linux/amd64** (the OCI Ampere A1 shape is arm64).
