# Model Selection Report

## Existing Goldy Models In This Project

The current Goldy registry in OG Runner already covers:

1. Governance capture risk
2. Cross-chain bridge risk
3. DeFi protocol health
4. Stablecoin depeg risk
5. NFT wash trading

## Gap Chosen

A DEX-specific liquidity durability model is not covered by the current Goldy set. The missing question is not "is the protocol alive?" but "will this venue still have usable depth when LPs leave, emissions fade, or swap flow turns toxic?"

## Selected Model

**DEX Liquidity Exit Risk Scorer**

Why this is the best fit:

- it does not duplicate governance, bridge, stablecoin, or NFT integrity coverage
- it is practical for treasury routing, LP allocation, and DeFi venue diligence
- its inputs are obtainable from public analytics sources
- it fits ONNX-friendly scoring because the frontend can shape and interpret the score deterministically

## Four Additional Unselected Ideas

1. **Treasury-Sell-Pressure-Forecaster** - predicts DAO token sell pressure from runway stress, unlocks, and treasury composition.
2. **Oracle-Manipulation-Surface-Scorer** - scores how exposed a protocol is to oracle manipulation via thin markets, lag, and collateral concentration.
3. **Yield-Sustainability-Risk-Monitor** - scores whether a DeFi yield source is organic or artificially subsidized.
4. **Governance-Bribe-Pressure-Scorer** - evaluates whether a governance system is becoming vulnerable to bribes, delegation capture, and turnout distortion.
