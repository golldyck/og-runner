# DEX Liquidity Exit Risk Scorer

DEX Liquidity Exit Risk Scorer estimates how likely a DEX venue or pool is to lose usable liquidity before traders fully price in the fragility. It is designed for operators, treasury teams, LPs, and DeFi investors who want an early warning signal before spreads widen, slippage spikes, and LP capital leaves the venue.

## Overview

Most DeFi risk models focus on protocol insolvency, bridge custody, governance capture, or stablecoin peg stress. A separate failure mode exists in AMMs and DEX venues: a market can stay online while still becoming functionally unsafe because liquidity is concentrated, incentive-driven, and already under withdrawal pressure.

This model targets that specific gap. It scores the risk that a DEX loses real execution quality because large LPs exit, emissions stop subsidizing liquidity, token unlocks hit, or swap flow turns persistently one-sided. Instead of asking whether the protocol still exists, it asks whether traders and LPs will still trust the venue with meaningful size.

The model is especially useful when comparing DEX venues that appear healthy on headline TVL alone. TVL is only one layer. The more important question is whether that liquidity is durable, distributed, and economically justified without incentives.

## Scoring Architecture

The model outputs a `liquidity_exit_risk_score` from 0 to 100 where higher scores mean a greater probability of meaningful liquidity degradation. The score is constructed from five pillars:

- `liquidity_depth` (28%)
- `concentration_risk` (22%)
- `flow_instability` (22%)
- `incentive_dependence` (18%)
- `governance_safety` (10%)

The final score is a weighted combination of these pillars. Each pillar is itself built from open-source on-chain and market structure features that can be sourced from DeFiLlama, DEX analytics dashboards, token unlock trackers, and governance metadata.

## Pillar 1 - Liquidity Depth (weight: 28%)

**What it measures:** Whether the venue still has enough real depth to absorb trades without collapsing execution quality.

**Input features:**
- `pool_tvl_usd` - current usable liquidity in the venue or pool
- `slippage_100k_buy_pct` - buy-side slippage for a $100k equivalent trade
- `slippage_100k_sell_pct` - sell-side slippage for a $100k equivalent trade

**Scoring logic:**
- lower TVL relative to venue size raises risk
- high buy or sell slippage raises risk quickly
- shallow depth is treated as an immediate fragility signal

## Pillar 2 - Concentration Risk (weight: 22%)

**What it measures:** Whether a small number of actors can destabilize the venue by removing liquidity.

**Input features:**
- `lp_top10_share` - share of liquidity controlled by the top LP wallets
- `top_pool_share_of_protocol` - dependence on one dominant pool inside the venue
- `bridge_dependent_liquidity_share` - share of liquidity that depends on bridged assets or bridge assumptions

**Scoring logic:**
- higher LP concentration raises exit risk
- venues dominated by one pool are less resilient
- heavy bridge dependence adds fragility when cross-chain liquidity weakens

## Pillar 3 - Flow Instability (weight: 22%)

**What it measures:** Whether recent liquidity and swap behavior shows that capital is already starting to leave.

**Input features:**
- `liquidity_7d_change` - weekly liquidity drain or growth
- `liquidity_30d_change` - monthly liquidity trend
- `whale_lp_exit_7d` - large LP withdrawal pressure
- `net_swap_flow_7d` - directional flow imbalance over the last week
- `unique_lp_count` - LP breadth and diversification

**Scoring logic:**
- negative liquidity change raises risk
- large LP exits are treated as a high-signal warning
- persistent one-sided swap flow raises instability
- low LP breadth makes recovery harder

## Pillar 4 - Incentive Dependence (weight: 18%)

**What it measures:** Whether liquidity is staying because it is economically healthy or because emissions are temporarily subsidizing it.

**Input features:**
- `incentive_apr` - APR from emissions or token rewards
- `fee_apr` - APR supported by real fees
- `emissions_30d_usd` - 30-day emissions budget
- `emissions_to_fees_ratio` - incentive dependence versus organic fee generation
- `token_unlock_30d_usd` - short-term unlock overhang

**Scoring logic:**
- high emissions relative to fees raises risk
- incentives materially above fees imply weaker organic demand
- large unlocks increase the probability of LP and treasury sell pressure

## Pillar 5 - Governance Safety (weight: 10%)

**What it measures:** Whether the venue can react safely to stress without introducing avoidable execution or admin risk.

**Input features:**
- `governance_timelock_hours` - timelock duration on sensitive changes
- `audit_count` - independent audits completed
- `exploit_history_count` - prior exploit record
- `oracle_dependency_score` - dependence on oracles for routing or pricing
- `correlated_asset_risk` - correlated asset exposure inside the venue
- `treasury_lp_share` - treasury support in venue liquidity
- `protocol_owned_liquidity_share` - durable protocol-owned depth

**Scoring logic:**
- short timelocks and weak audits raise risk
- exploit history raises structural caution
- high oracle and asset correlation dependence raises systemic fragility
- durable protocol-owned liquidity helps offset pure mercenary depth

## Input Schema

```json
{
  "pool_tvl_usd": 120000000,
  "liquidity_7d_change": -0.08,
  "liquidity_30d_change": -0.04,
  "lp_top10_share": 0.58,
  "treasury_lp_share": 0.12,
  "protocol_owned_liquidity_share": 0.21,
  "incentive_apr": 0.18,
  "fee_apr": 0.07,
  "emissions_30d_usd": 4200000,
  "emissions_to_fees_ratio": 1.8,
  "volume_tvl_ratio_7d": 0.46,
  "slippage_100k_buy_pct": 0.012,
  "slippage_100k_sell_pct": 0.015,
  "bridge_dependent_liquidity_share": 0.28,
  "whale_lp_exit_7d": 0.09,
  "net_swap_flow_7d": -0.06,
  "unique_lp_count": 1480,
  "top_pool_share_of_protocol": 0.42,
  "token_unlock_30d_usd": 18000000,
  "governance_timelock_hours": 48,
  "audit_count": 3,
  "exploit_history_count": 0,
  "oracle_dependency_score": 0.34,
  "correlated_asset_risk": 0.26
}
```

## Output Schema

```json
{
  "liquidity_exit_risk_score": 47.2,
  "grade": "C",
  "risk_level": "MEDIUM",
  "pillar_scores": {
    "liquidity_depth": 31.4,
    "concentration_risk": 44.8,
    "flow_instability": 55.0,
    "incentive_dependence": 63.1,
    "governance_safety": 22.3
  },
  "flags": [
    "INCENTIVE_DEPENDENCE",
    "LP_CONCENTRATION"
  ]
}
```

## Score Grades

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 0-20 | A | Very durable liquidity profile |
| 21-40 | B | Mostly resilient but not stress-proof |
| 41-60 | C | Moderate fragility under adverse flows |
| 61-80 | D | High likelihood of meaningful liquidity deterioration |
| 81-100 | F | Severe exit risk and execution fragility |

## Flags System

| Flag ID | Trigger Condition | Severity |
|---------|-------------------|----------|
| `LP_CONCENTRATION` | `lp_top10_share > 0.60` | High |
| `WHALE_EXIT_PRESSURE` | `whale_lp_exit_7d > 0.10` | High |
| `INCENTIVE_DEPENDENCE` | `emissions_to_fees_ratio > 1.25` | High |
| `SHORT_TIMELOCK` | `governance_timelock_hours < 24` | Medium |
| `SHALLOW_DEPTH` | `slippage_100k_buy_pct > 0.02` | High |
| `NO_MAJOR_TRIGGER` | No major flag condition triggered | Informational |

## Use Cases

1. **DEX treasury management** - decide whether to continue subsidizing a venue or pool.
2. **LP due diligence** - compare where liquidity is durable versus purely incentive-driven.
3. **Token launch routing** - choose a launch venue with lower exit-risk and better depth durability.
4. **Risk research** - benchmark DEX venues before routing treasury swaps or market-making capital.

## Data Sources

- **Protocol TVL and trends:** DeFiLlama
- **Volume, slippage, pool concentration:** DEX dashboards, analytics APIs, The Graph
- **Unlock schedule and emissions:** token dashboards, governance forums, tokenomics trackers
- **Governance and audit context:** protocol docs, governance portals, audit reports

## Model Versioning

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-03-29 | Initial release |

## Tags

#defi #dex #liquidity #risk #market-structure #onchain
