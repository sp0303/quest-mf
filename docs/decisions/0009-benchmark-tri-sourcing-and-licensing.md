# 0009. Benchmark TRI Sourcing and Licensing Governance

* **Status**: Accepted (Option B Approved for Production; Option A Designated Research-Only)
* **Date**: 2026-09-19
* **Deciders**: Engineering & Quant Team, Project Owner
* **Consulted**: `docs/mf_quant_screener_spec_v2.md` §22, §31; `AGENTS.md` §10

---

## 1. Context and Problem Statement

Rule **Q5** of the Quant Specification (`docs/mf_quant_screener_spec_v2.md`) mandates:
> *"Fund and benchmark returns use identical start and end dates. Benchmarks are TRI (Total Return Index); PRI is flagged and excluded from alpha scoring."*

To satisfy Q5 across Indian equity mutual funds, the system requires historical and daily TRI series for primary benchmarks:
- `NIFTY 50 TRI` (Large-Cap)
- `NIFTY Next 50 TRI` (Large-Cap / Large-Mid)
- `NIFTY Midcap 150 TRI` (Mid-Cap)
- `NIFTY Smallcap 250 TRI` (Small-Cap)
- `NIFTY 500 TRI` (Multi-Cap / Flexi-Cap)

`docs/mf_quant_screener_spec_v2.md` §31 (Open Decisions, item 18) explicitly marks **"Benchmark-data licensing for any external sharing"** as an open, unresolved governance decision. Furthermore, `AGENTS.md` §10 stipulates that agents must stop and ask when external publishing, credentials, or data licensing questions arise.

Currently, `backend/workers/benchmark_worker.py` retrieves benchmark TRI data by querying:
```text
https://www.niftyindices.com/Backpage/getTotalReturnIndexString
```
This is an undocumented ASP.NET internal handler powering client-side UI widgets on the NSE Indices public website, requiring simulated browser headers (`User-Agent: Mozilla/5.0 ...`) and synchronous payload formatting.

---

## 2. Risk Analysis of Current Implementation

1. **Licensing & Terms of Use (High Governance Risk)**:
   - NSE Indices (IISL) terms of service restrict automated scraping, bulk extraction, and commercial redistribution of proprietary index series without an authorized data-feed license.
   - Using this data for private offline research is common, but redistributing it, publishing it on a public web application, or serving commercial users creates legal exposure.
2. **Operational Fragility**:
   - Internal ASP.NET endpoints are unversioned and can be modified, rate-limited, or protected behind Cloudflare/CAPTCHA without notice.
   - If the endpoint breaks, benchmark updates stall, causing Rule Q5 checks to fail and halting the daily scoring pipeline.
3. **Data Integrity & Traceability**:
   - Payload formatting changes could silently corrupt return series if not strictly guarded by schema validation.

---

## 3. Evaluated Options

### Option A: Retain Scraping for Research/Staging, Gate External Publishing (Current Interim Baseline)
- **Description**: Continue utilizing `benchmark_worker.py` with strict rate-limiting (<= 1 req/s) and local caching for private research and staging backtests only. Strip benchmark TRI publication from any unauthenticated public API or commercial tier.
- **Pros**: Zero financial cost; provides exact historical TRI numbers back to 2013.
- **Cons**: High legal risk if exposed externally; fragile pipeline subject to upstream breakage.

### Option B: Canonical Direct-Growth Index Mutual Fund Proxies (AMFI Open-Data Zero-Risk Alternative)
- **Description**: Replace raw index scraping with AMFI daily Direct-Growth NAVs of institutional low-cost index funds with near-zero tracking error:
  - Large Cap: UTI / Nippon / HDFC Nifty 50 Index Fund Direct-G (TER ~0.10%)
  - Large-Mid: Motilal Oswal / ICICI Nifty Next 50 Index Fund Direct-G
  - Mid Cap: Motilal Oswal Nifty Midcap 150 Index Fund Direct-G
  - Small Cap: Nippon India Nifty Smallcap 250 Index Fund Direct-G
  - Broad: Motilal Oswal Nifty 500 Index Fund Direct-G
- **Pros**:
  - 100% legal, open data via AMFI daily feed (`NAVAll.txt`).
  - Completely immune to scraping bans or licensing disputes.
  - Accounts for real-world frictions (cash drag, transaction costs) that real benchmark followers experience.
- **Cons**:
  - Inception dates for some Direct-Growth Midcap/Smallcap index funds start in 2018–2020, requiring stitching or proxies before 2018.
  - Slight expense drag (~10–20 bps/yr) vs pure mathematical index.

### Option C: Commercial NSE Indices Data Subscription (Institutional Compliance)
- **Description**: Enter into an official data vendor agreement with NSE Data & Analytics for historical and daily End-of-Day (EOD) Total Return Index feeds.
- **Pros**: 100% contractually compliant; official SLA; indemnified for commercial distribution.
- **Cons**: Significant annual recurring cost (typically thousands of USD/year); requires an established corporate entity and compliance reporting.

---

## 4. Recommendation & Proposed Decision

1. **Short-Term (Development & Offline Research)**:
   - Accept **Option A** with strict rate-limiting (<= 1 req/s) and persistent storage in `var/data/raw/` for private research and local backtesting.
2. **Production & Public UI (Zero-Docker / Web Launch)**:
   - Adopt **Option B** as the default publicly publishable benchmark tier (labeled "Investable Benchmark Proxy (Direct Index Fund)"), eliminating all legal risk and external data costs.
   - Revisit **Option C** only if external funding or institutional client demands necessitate official proprietary index certification.

---

## 5. Recorded Decision & Next Actions
 
- [x] **Approved 2026-09-19**: Option B adopted as the canonical, production-ready benchmark pipeline.
- [x] Option A (NSE scraping) isolated strictly for offline research / validation, barred from public endpoints.
- [x] Disclosure added to `docs/results/HOLDOUT_EVALUATION_REPORT.md`.
- [x] Index proxy scheme codes mapped and implemented in `backend/workers/benchmark_worker.py`.
