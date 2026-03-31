# Cross DEX Arbitrage Pressure Index

Cross DEX Arbitrage Pressure Index estimates how much arbitrage pressure is building across DEX venues for the same asset pair before execution quality breaks down for regular users.

## Overview

DeFi users often see a simple price on one venue and assume market quality is stable. In practice, fragmented liquidity, routing friction, and gas spikes can cause large cross-venue dislocations where only fast actors can extract value. This can produce hidden cost for normal traders even when aggregate TVL still looks healthy.

Most public DeFi models on the hub focus on volatility, return prediction, protocol-level risk, or stablecoin stress. A specific gap remains in cross-venue execution pressure analysis: understanding when spread opportunities are not healthy price discovery but a warning signal that markets are becoming structurally inefficient.

This model scores arbitrage pressure from open on-chain and market structure features. Higher scores indicate stronger evidence that the pair is entering a stressed execution regime with elevated extraction risk, unstable routing, and weaker fill quality for normal flow.

## Scoring Architecture

The model outputs `arbitrage_pressure_score` from 0 to 100 (higher = more pressure).

Weighted pillars:
- `price_dislocation` (30%)
- `execution_friction` (24%)
- `liquidity_fragmentation` (22%)
- `flow_imbalance` (14%)
- `resilience_context` (10%)

The score is computed from normalized feature blocks and then mapped into grade bands. The ONNX artifact is intentionally lightweight and deterministic for hub compatibility; detailed interpretation is done at the application layer using the same feature set.

## Pillar 1 - Price Dislocation (weight: 30%)

**What it measures:** Persistent and abnormal cross-venue spread behavior.

**Input features:**
- `spread_median_bps_5m` - median spread across tracked DEX venues in 5-minute window
- `spread_p95_bps_5m` - p95 spread in 5-minute window
- `spread_median_bps_1h` - median spread in 1-hour window
- `cross_venue_price_std_bps` - standard deviation of venue mid-prices

**Scoring logic:**
- wider and more persistent spread widens pressure score
- high p95 relative to median indicates bursty instability
- higher cross-venue price dispersion signals degraded convergence

## Pillar 2 - Execution Friction (weight: 24%)

**What it measures:** Whether profitable dislocations are blocked by execution costs and route fragility.

**Input features:**
- `gas_cost_usd_p50` - median execution gas cost
- `gas_cost_usd_p95` - p95 execution gas cost
- `slippage_100k_buy_bps` - buy-side slippage for $100k equivalent
- `slippage_100k_sell_bps` - sell-side slippage for $100k equivalent
- `failed_swap_rate_1h` - failed or reverted swap ratio in the last hour

**Scoring logic:**
- high gas and slippage convert benign spread into harmful pressure
- elevated failure rate indicates route fragility and execution uncertainty

## Pillar 3 - Liquidity Fragmentation (weight: 22%)

**What it measures:** How split and brittle liquidity is across venues.

**Input features:**
- `top_venue_depth_share` - share of total depth concentrated in top venue
- `venue_count_active` - number of venues with meaningful depth and activity
- `depth_imbalance_ratio` - asymmetry between buy and sell side depth
- `bridge_settlement_share` - share requiring bridge-dependent settlement assumptions

**Scoring logic:**
- concentration in one venue raises shock sensitivity
- low active venue count raises pressure
- high depth imbalance increases adverse selection risk
- bridge-dependent execution adds failure pathways

## Pillar 4 - Flow Imbalance (weight: 14%)

**What it measures:** Whether flow dynamics are currently amplifying dislocations.

**Input features:**
- `net_flow_5m_usd` - signed net flow in short window
- `net_flow_1h_usd` - signed net flow in one-hour window
- `whale_swap_share_1h` - share of flow from large swaps
- `toxic_flow_proxy` - proxy for informed or adverse flow

**Scoring logic:**
- one-directional flow and high whale dominance raise pressure
- elevated toxic flow proxy means convergence is less accessible to normal traders

## Pillar 5 - Resilience Context (weight: 10%)

**What it measures:** Market context that can dampen or amplify pressure.

**Input features:**
- `realized_vol_1h` - realized volatility over one hour
- `event_risk_flag` - binary event risk indicator (upgrade/news/market shock)
- `oracle_deviation_bps` - venue median vs reference oracle gap

**Scoring logic:**
- high volatility and event risk reduce market resilience
- larger oracle deviation supports pressure regime classification

## Input Schema

```json
{
  "spread_median_bps_5m": 14.2,
  "spread_p95_bps_5m": 44.7,
  "spread_median_bps_1h": 11.8,
  "cross_venue_price_std_bps": 9.6,
  "gas_cost_usd_p50": 3.8,
  "gas_cost_usd_p95": 12.4,
  "slippage_100k_buy_bps": 36.0,
  "slippage_100k_sell_bps": 41.5,
  "failed_swap_rate_1h": 0.032,
  "top_venue_depth_share": 0.61,
  "venue_count_active": 4.0,
  "depth_imbalance_ratio": 1.42,
  "bridge_settlement_share": 0.27,
  "net_flow_5m_usd": -240000.0,
  "net_flow_1h_usd": -1700000.0,
  "whale_swap_share_1h": 0.49,
  "toxic_flow_proxy": 0.57,
  "realized_vol_1h": 0.021,
  "event_risk_flag": 1.0,
  "oracle_deviation_bps": 18.3
}
```

## Output Schema

```json
{
  "arbitrage_pressure_score": 68.4,
  "grade": "D",
  "pressure_level": "HIGH",
  "pillar_scores": {
    "price_dislocation": 74.1,
    "execution_friction": 66.2,
    "liquidity_fragmentation": 61.8,
    "flow_imbalance": 70.3,
    "resilience_context": 55.0
  },
  "flags": [
    "SPREAD_PERSISTENCE",
    "FRAGMENTED_DEPTH",
    "EXECUTION_FRICTION"
  ]
}
```

## Score Grades

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 0-20 | A | Healthy convergence and low extraction pressure |
| 21-40 | B | Mild pressure with manageable execution conditions |
| 41-60 | C | Moderate pressure and elevated route fragility |
| 61-80 | D | High pressure and likely user execution degradation |
| 81-100 | F | Severe pressure regime with unstable cross-venue convergence |

## Flags System

| Flag ID | Trigger Condition | Severity |
|---------|-------------------|----------|
| `SPREAD_PERSISTENCE` | `spread_median_bps_5m > 12` and `spread_median_bps_1h > 10` | High |
| `TAIL_DISLOCATION` | `spread_p95_bps_5m > 40` | High |
| `EXECUTION_FRICTION` | `gas_cost_usd_p95 > 10` or slippage side > 35 bps | High |
| `FRAGMENTED_DEPTH` | `top_venue_depth_share > 0.55` and `venue_count_active < 5` | Medium |
| `FLOW_STRESS` | `abs(net_flow_1h_usd) > 1200000` and `whale_swap_share_1h > 0.45` | Medium |
| `ORACLE_GAP` | `oracle_deviation_bps > 15` | Medium |

## Use Cases

1. **DEX risk desks** - monitor when cross-venue divergence is becoming toxic for users.
2. **Routing engines** - reduce route size or change venue weighting under high pressure.
3. **Market makers** - calibrate inventory and quote width against pressure regimes.
4. **Treasury execution teams** - time large swaps to avoid stress windows.

## Data Sources

- **DEX prices, spreads, swaps, depth:** DEX APIs, on-chain indexers, The Graph
- **Network fees and failure rates:** chain RPC metrics and transaction traces
- **Reference prices:** oracle feeds (Pyth/Chainlink) and venue medians
- **Event context:** protocol governance calendars and public market event feeds

## Model Versioning

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-04-01 | Initial release |

## Tags

#defi #dex #arbitrage #risk #market-structure #onchain
