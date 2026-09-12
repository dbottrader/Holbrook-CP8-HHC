# CP8 Multi-Agent Financial Intelligence Benchmark v0.1

**Status:** EXPERIMENTAL / PAPER BENCHMARK
**Issue:** #31
**Rule:** evidence earns promotion; narrative does not.

## Objective
Test whether a provenance-preserving collective of independent AI forecasts adds measurable predictive value over individual agents and simple baselines.

This benchmark does **not** promise profit, provide investment advice, or authorize live-money trading.

## Frozen protocol
1. **Universe:** initially SPY, QQQ, DIA, IWM, GLD, TLT, and BTC-USD where reliable common data is available. The universe may be reduced before the first prediction window if data availability is unequal, but cannot be changed after predictions for that window are sealed.
2. **Forecast target:** next-window direction and expected return. Initial horizon: 1 trading day for exchange-traded assets; BTC uses the corresponding UTC daily close window.
3. **Information cutoff:** no information published after the prediction timestamp may enter that prediction.
4. **Submission:** asset, timestamp, horizon, direction, expected return, confidence, rationale/evidence references, agent/model identifier, model version if available, and input-data hash.
5. **Independence:** agents submit before seeing peer predictions. Meta-model aggregation occurs only after individual submissions are sealed.
6. **Baselines:** buy-and-hold, previous-close direction, simple momentum, and equal-weight collective forecast.
7. **Meta-model:** initial equal-weight ensemble. Any learned weighting must be predeclared and trained only on prior resolved observations, never on the active evaluation window.
8. **Costs:** report gross results first; then sensitivity to explicit transaction-cost assumptions. No hidden leverage.
9. **Evaluation:** strictly out-of-sample. Minimum sample size must be reached before any champion claim.
10. **Failures:** preserve abstentions, missing data, losing forecasts, contradictions, and failed runs. Never delete an unfavorable observation.

## Required metrics
- directional accuracy
- Brier/log-style calibration metrics where applicable
- mean absolute return error
- cumulative paper return
- volatility
- maximum drawdown
- turnover
- cost sensitivity
- benchmark-relative return
- performance by asset and horizon
- individual-agent versus ensemble contribution

## Five-field evidence record
Every material result must separate:

- **OBSERVED:** directly measured/retrieved fact.
- **CONTEXT:** data source, cutoff, environment, and boundary.
- **INFERENCE:** interpretation of the observation.
- **TEST:** reproducible test that could support or falsify the inference.
- **CONCLUSION:** bounded current verdict: PASS, FAIL, or HOLD/BLOCKED.

## Anti-leakage rules
- prediction timestamps are authoritative;
- evaluation data must occur after the information cutoff;
- no retroactive feature changes for an open evaluation window;
- no cherry-picking assets or windows after seeing outcomes;
- no replacement of losing predictions;
- all code/data-version changes are recorded;
- source and output hashes are retained where technically possible.

## Promotion gates
A result remains **HOLD** until the ledger, scoring implementation, data provenance, and replay procedure can be independently inspected. A temporary leaderboard is descriptive only. "Champion" means best measured result under the frozen protocol, not general superiority.

## First execution target
Produce a machine-readable prediction ledger and one bounded paper-trading evaluation window. Publish the receipt even if the result is negative or blocked.
