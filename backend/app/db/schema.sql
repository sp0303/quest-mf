-- quest-mf database schema initialization

-- 1. SCHEMAS
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS scoring;
CREATE SCHEMA IF NOT EXISTS backtest;
CREATE SCHEMA IF NOT EXISTS auth;

-- 2. OPS
CREATE TABLE IF NOT EXISTS ops.data_snapshots (
    snapshot_id   SERIAL PRIMARY KEY,
    as_of_date    DATE        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    git_sha       TEXT        NOT NULL DEFAULT 'initial',
    status        TEXT        NOT NULL CHECK (status IN ('BUILDING','PUBLISHED','FAILED')),
    notes         JSONB
);
CREATE INDEX IF NOT EXISTS idx_snapshots_as_of ON ops.data_snapshots (as_of_date DESC);

CREATE TABLE IF NOT EXISTS ops.ingest_log (
    ingest_id     BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,
    source_url    TEXT        NOT NULL,
    business_date DATE,
    raw_sha256    TEXT        NOT NULL,
    object_key    TEXT        NOT NULL,
    parser_ver    TEXT        NOT NULL,
    rows_in       INT         NOT NULL,
    rows_loaded   INT         NOT NULL,
    rows_rejected INT         NOT NULL,
    retrieved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, raw_sha256)
);

CREATE TABLE IF NOT EXISTS ops.dq_issues (
    issue_id      BIGSERIAL PRIMARY KEY,
    ingest_id     BIGINT REFERENCES ops.ingest_log,
    check_name    TEXT NOT NULL,
    severity      TEXT NOT NULL CHECK (severity IN ('INFO','WARN','BLOCK')),
    entity_key    TEXT NOT NULL,
    details       JSONB,
    resolved      BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. REF
CREATE TABLE IF NOT EXISTS ref.amcs (
    amc_id     SMALLSERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ref.categories (
    category_id SMALLSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    asset_class TEXT NOT NULL DEFAULT 'EQUITY',
    ref_benchmark_id SMALLINT
);

CREATE TABLE IF NOT EXISTS ref.benchmarks (
    benchmark_id SMALLSERIAL PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    label        TEXT NOT NULL,
    provider     TEXT NOT NULL DEFAULT 'NSE',
    is_tri       BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS ref.portfolios (
    portfolio_id  SERIAL PRIMARY KEY,
    display_name  TEXT NOT NULL,
    amc_id        SMALLINT NOT NULL REFERENCES ref.amcs,
    launch_date   DATE,
    closed_date   DATE,
    close_reason  TEXT
);
CREATE INDEX IF NOT EXISTS idx_portfolios_name ON ref.portfolios (display_name);

CREATE TABLE IF NOT EXISTS ref.schemes (
    scheme_code   INT PRIMARY KEY,
    portfolio_id  INT NOT NULL REFERENCES ref.portfolios,
    isin_payout   TEXT,
    isin_reinvest TEXT,
    scheme_name   TEXT NOT NULL,
    plan          TEXT NOT NULL CHECK (plan IN ('DIRECT','REGULAR')),
    option        TEXT NOT NULL CHECK (option IN ('GROWTH','IDCW','BONUS')),
    inception_date DATE,
    status        TEXT NOT NULL CHECK (status IN ('ACTIVE','CLOSED')),
    is_canonical  BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_schemes_canonical ON ref.schemes (portfolio_id) WHERE is_canonical;

CREATE TABLE IF NOT EXISTS ref.category_history (
    id            SERIAL PRIMARY KEY,
    portfolio_id  INT NOT NULL REFERENCES ref.portfolios,
    valid_from    DATE NOT NULL,
    valid_to      DATE NOT NULL DEFAULT '9999-12-31',
    category_id   SMALLINT NOT NULL REFERENCES ref.categories,
    mapping_confidence REAL NOT NULL DEFAULT 1.0,
    source_url    TEXT
);
CREATE INDEX IF NOT EXISTS idx_cat_hist ON ref.category_history (portfolio_id, valid_from, valid_to);

CREATE TABLE IF NOT EXISTS ref.benchmark_history (
    id            SERIAL PRIMARY KEY,
    portfolio_id  INT NOT NULL REFERENCES ref.portfolios,
    valid_from    DATE NOT NULL,
    valid_to      DATE NOT NULL DEFAULT '9999-12-31',
    benchmark_id  SMALLINT NOT NULL REFERENCES ref.benchmarks,
    tier          SMALLINT NOT NULL DEFAULT 1,
    source_url    TEXT
);

CREATE TABLE IF NOT EXISTS ref.subscription_status (
    id            SERIAL PRIMARY KEY,
    portfolio_id  INT NOT NULL REFERENCES ref.portfolios,
    valid_from    DATE NOT NULL,
    valid_to      DATE NOT NULL DEFAULT '9999-12-31',
    status        TEXT NOT NULL CHECK (status IN ('OPEN','LUMPSUM_RESTRICTED','SIP_ONLY','SUSPENDED')),
    note          TEXT
);

CREATE TABLE IF NOT EXISTS ref.ter_history (
    scheme_code    INT  NOT NULL REFERENCES ref.schemes,
    effective_date DATE NOT NULL,
    ter            REAL NOT NULL,
    base_ter       REAL,
    PRIMARY KEY (scheme_code, effective_date)
);

CREATE TABLE IF NOT EXISTS ref.load_rules (
    id             SERIAL PRIMARY KEY,
    scheme_code    INT NOT NULL REFERENCES ref.schemes,
    valid_from     DATE NOT NULL,
    valid_to       DATE NOT NULL DEFAULT '9999-12-31',
    exit_load_rate REAL,
    exit_load_days SMALLINT,
    rule_text      TEXT NOT NULL
);

-- 4. MARKET
CREATE TABLE IF NOT EXISTS market.nav_history (
    scheme_code  INT           NOT NULL,
    nav_date     DATE          NOT NULL,
    nav          NUMERIC(18,6) NOT NULL CHECK (nav > 0),
    ingest_id    BIGINT        NOT NULL DEFAULT 1,
    revision     SMALLINT      NOT NULL DEFAULT 0,
    PRIMARY KEY (scheme_code, nav_date)
);
CREATE INDEX IF NOT EXISTS idx_nav_date ON market.nav_history (nav_date);

CREATE TABLE IF NOT EXISTS market.benchmark_values (
    benchmark_id SMALLINT NOT NULL,
    value_date   DATE     NOT NULL,
    value        NUMERIC(18,4) NOT NULL,
    ingest_id    BIGINT   NOT NULL DEFAULT 1,
    PRIMARY KEY (benchmark_id, value_date)
);

CREATE TABLE IF NOT EXISTS market.risk_free (
    series     TEXT NOT NULL,
    rate_date  DATE NOT NULL,
    annual_yield REAL NOT NULL,
    PRIMARY KEY (series, rate_date)
);

-- 5. ANALYTICS
CREATE TABLE IF NOT EXISTS analytics.rolling_metrics (
    portfolio_id     INT      NOT NULL,
    window_code      TEXT     NOT NULL,
    end_date         DATE     NOT NULL,
    start_date       DATE     NOT NULL,
    n_obs            SMALLINT NOT NULL,
    ret              REAL NOT NULL,
    log_ret          REAL NOT NULL,
    bench_ret        REAL,
    active_ret       REAL,
    max_dd           REAL,
    vol_ann          REAL,
    downside_dev_ann REAL,
    flags            SMALLINT NOT NULL DEFAULT 0,
    PRIMARY KEY (portfolio_id, window_code, end_date)
);
CREATE INDEX IF NOT EXISTS idx_rolling_lookup ON analytics.rolling_metrics (portfolio_id, window_code, end_date DESC);

CREATE TABLE IF NOT EXISTS analytics.fund_summary (
    portfolio_id INT PRIMARY KEY,
    as_of_date   DATE NOT NULL,
    payload      JSONB NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. SCORING
CREATE TABLE IF NOT EXISTS scoring.model_versions (
    model_version TEXT PRIMARY KEY,
    config        JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_default    BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS scoring.scores (
    portfolio_id  INT  NOT NULL,
    as_of_date    DATE NOT NULL,
    model_version TEXT NOT NULL,
    momentum      REAL,
    persistence   REAL,
    lt_quality    REAL,
    risk          REAL,
    cost          REAL,
    composite     REAL,
    confidence    SMALLINT NOT NULL,
    quadrant      SMALLINT,
    flags         INT NOT NULL DEFAULT 0,
    PRIMARY KEY (portfolio_id, model_version, as_of_date)
);

CREATE TABLE IF NOT EXISTS scoring.screener_snapshot (
    as_of_date    DATE     NOT NULL,
    model_version TEXT     NOT NULL,
    category_id   SMALLINT NOT NULL,
    portfolio_id  INT      NOT NULL,
    fund_name     TEXT     NOT NULL,
    amc           TEXT     NOT NULL,
    ret_1m        REAL,
    ret_3m        REAL,
    ret_6m        REAL,
    ret_1y        REAL,
    cagr_3y       REAL,
    shp_3m        REAL,
    peer_pct_3m   REAL,
    alpha_3m      REAL,
    ir_3y         REAL,
    mdd_3y        REAL,
    ter           REAL,
    exit_load_rate REAL,
    exit_load_days SMALLINT,
    composite     REAL,
    confidence    SMALLINT,
    quadrant      SMALLINT,
    flags         INT NOT NULL DEFAULT 0,
    investable    BOOLEAN NOT NULL DEFAULT true,
    PRIMARY KEY (as_of_date, model_version, category_id, portfolio_id)
);
CREATE INDEX IF NOT EXISTS idx_screener_query ON scoring.screener_snapshot
    (as_of_date, model_version, category_id, composite DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS scoring.latest (
    model_version TEXT PRIMARY KEY,
    as_of_date    DATE NOT NULL,
    published_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. BACKTEST
CREATE TABLE IF NOT EXISTS backtest.runs (
    run_id         BIGSERIAL PRIMARY KEY,
    created_by     TEXT NOT NULL,
    model_version  TEXT NOT NULL,
    config         JSONB NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED','CANCELLED')),
    progress_pct   REAL NOT NULL DEFAULT 0,
    summary        JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS backtest.run_series (
    run_id   BIGINT NOT NULL REFERENCES backtest.runs,
    series   TEXT   NOT NULL,
    d        DATE   NOT NULL,
    v        REAL   NOT NULL,
    PRIMARY KEY (run_id, series, d)
);

-- 8. AUTH
CREATE TABLE IF NOT EXISTS auth.users (
    user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('viewer','analyst','admin')),
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
