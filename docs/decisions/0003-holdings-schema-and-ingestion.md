# 0003. Fund Portfolio Holdings, Market-Cap Classification, and Overlap Architecture

* **Status**: Accepted
* **Date**: 2026-09-20
* **Deciders**: Engineering & Quant Team, Project Owner
* **Consulted**: `docs/mf_quant_screener_spec_v2.md` §30 (Roadmap Phase 9), §6.1, §6.2; `AGENTS.md` §1, §3 (Rules 1, 3, 4, 7, 9)

---

## 1. Context and Problem Statement

Retail mutual fund platforms in India (Groww, Zerodha Coin, Paytm Money, Value Research) present descriptive fund factsheets:
- Top 10 equity holdings (stock, sector, % to NAV)
- Sector breakdown (Financials, IT, Healthcare, etc.)
- Market-cap split (Large Cap %, Mid Cap %, Small Cap %, Cash %)
- Fund profile metadata (AUM, Fund Manager, Riskometer, Turnover Ratio, P/E, P/B)

While `quest-mf` excels in its core quant engine (rolling returns, benchmark TRI alpha, 2x2 quadrant rankings, walk-forward backtests), it lacked basic portfolio transparency. Furthermore, investors struggle with identifying **portfolio overlap** (duplicate stock holdings across multiple funds), a metric virtually no free Indian platform calculates with mathematical rigor.

However, ingesting portfolio disclosures from 40+ AMCs presents high operational maintenance risks due to fragmented Excel formatting across AMCs.

---

## 2. Decision Drivers

1. **Feature Parity with Rigorous Differentiation**:
   - Provide standard holdings, sector allocations, and market-cap splits.
   - Differentiate with a pure quant **Pairwise Portfolio Overlap Engine**:
     $$\text{Overlap}(A, B) = \sum_{i \in A \cap B} \min(w_{A,i}, w_{B,i})$$
2. **Point-in-Time Lag & Regulatory Transparency (Rules Q1 & Q16)**:
   - Holdings are disclosed monthly with a 10-day lag. Disclosed dates must be explicitly displayed.
3. **Precomputation Over Request-Time Compute (Rule 1)**:
   - Summary statistics (top-10 concentration, cap split, sector weights) must be precomputed into `holdings.portfolio_summary` so API requests remain fast `SELECT`s.
4. **Maintenance Mitigation (Top 5 AMCs First)**:
   - Target the top 5 AMCs (Nippon India, HDFC, ICICI Prudential, SBI, Kotak) covering >60% of equity AUM before expanding to other AMCs.
5. **Standardized Market Cap Classification**:
   - Use AMFI's semi-annual official list (Rank 1–100: Large Cap, 101–250: Mid Cap, 251+: Small Cap) stored in `ref.stock_market_cap`.

---

## 3. Decision

### 3.1 Database Schema
We establish a dedicated `holdings` schema and extend the `ref` schema:
1. **`ref.securities`**: Central security master keyed by 12-character Indian ISIN, containing security name, NSE symbol, and sector classification.
2. **`ref.stock_market_cap`**: Point-in-time market cap ranking from AMFI semi-annual disclosures (`valid_from`, `valid_to`, `market_cap_rank`, `market_cap_class`).
3. **`holdings.monthly_portfolio`**: Point-in-time monthly holdings per portfolio (`portfolio_id`, `as_of_date`, `isin`, `security_name`, `asset_type`, `sector`, `quantity`, `market_value_lakhs`, `pct_nav`, `disclosed_date`).
4. **`holdings.portfolio_summary`**: Precomputed summary (`portfolio_id`, `as_of_date`, `stock_count`, `top_10_concentration_pct`, `large_cap_pct`, `mid_cap_pct`, `small_cap_pct`, `cash_pct`, `sector_allocation`, `top_10_holdings`).
5. **`ref.fund_profile`**: Factsheet metadata per fund (`portfolio_id`, `fund_manager`, `aum_cr`, `ter_pct`, `portfolio_turnover_ratio`, `pe_ratio`, `pb_ratio`, `riskometer`, `min_sip_amount`).

### 3.2 Pure Quant Overlap Engine
- Implemented in `questmf_quant.portfolio.overlap` as a pure, unit-tested function:
  `compute_portfolio_overlap(weights_a, weights_b) -> OverlapResult`.
  Calculates joint overlap %, common holding count, and shared holding list.

### 3.3 UI Integration
- Enhance `FundDetailPage` with clean, accessible tabs:
  - **Overview**: Manager, AUM, Riskometer, P/E, Turnover, Min SIP.
  - **Holdings**: Top 10 holdings table, Sector allocation breakdown, Market-cap split bar.
  - **Risk & Quant**: Historical NAV chart, rolling metrics, Sharpe, Sortino, Drawdown.
  - **Portfolio Overlap**: Pairwise overlap comparison against any other fund or the top-ranked category peer.

---

## 4. Consequences

### Positive
- Delivers complete competitor parity on factsheet and holdings information.
- Establishes a major analytical differentiator with the Pairwise Overlap Engine.
- Standardizes stock classification using AMFI's official benchmark data.

### Neutral / Operational Trade-offs
- Monthly disclosure parsers require periodic validation when AMCs adjust Excel formats.
- Precomputed summaries require additional storage in the database.
