# ADR 0010 — Spec §16 composite (`v2_spec16`) and real cost inputs

**Status:** Accepted (2026-10-06)

## Context
QA of the live screener found the default model `v1_baseline` diverged from spec v2 §16:
- weights 35/25/20/10/10 instead of §16.2's 25/35/15/15/10;
- SHP was the persistence component, although §16.2 keeps SHP out of the V1 composite;
- features were absolute linear maps (`50 + r3m×250`, `50 + IR×25`, `100 + MDD×200`), not
  within-category percentiles (§16.1);
- cost was a constant 75, TER a constant 0.70%, exit load a constant 1%/365d for every fund;
- "3Y" IR and MDD were computed on whatever history existed (inflating young funds).

## Decision
1. New pure module `questmf_quant.composite` implements §16.1 exactly: within-category
   mid-rank percentiles (min 8 peers, Q8), inverted lower-is-better features, component =
   mean of non-null feature pcts (null if >50% null), composite = renormalised weighted mean,
   null + `INCOMPLETE` if more than one component is null.
2. Model `v2_spec16` (config in `scoring.model_versions`, Q13) becomes the default. `v1_baseline`
   rows are kept untouched for reproducibility.
3. Persistence uses benchmark-relative rolling windows (`questmf_quant.active`): 3M and 1Y
   beat %, 3M median active, 3Y IR (only with ≥756 obs, Q12).
4. Cost uses real Direct-plan TER from AMFI's official TER feed (`workers.ter_worker` →
   `ref.ter_history`, point-in-time). Exit-load days stay **null** until a genuine
   `load_rules` source exists — no fabricated defaults.
5. `flags` bitmask (§16.4): SMALL_PEER_GROUP=1, INCOMPLETE=2, SHORT_HISTORY=4,
   INVESTABILITY_UNVERIFIED=8, NO_BENCHMARK=16.
6. STT on equity-fund redemption corrected to 0.001% (§18), was 0.1%.

## Consequences
- Scores change for every fund; rankings are now peer-relative within category.
- The nightly job must run `workers.daily_scheduler --once` (NAV → benchmark → TER → compute);
  running only ingestion + compute left benchmarks frozen and `alpha_3m` null.
- Walk-forward evaluation of `v2_spec16` is pending (logged in `experiments/registry.csv`).
