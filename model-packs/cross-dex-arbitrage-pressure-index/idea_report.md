# Model Idea Research Snapshot

Date: 2026-04-01

## Hub Signals

- Total models on hub: `2274`
- Tasks available: `Language Models`, `DeFi Models`, `Risk Models`, `Multimodal`, `Protocol Optimization`
- Goldy models currently: 4

## Gap Summary

Direct arbitrage-pressure models are effectively missing:
- Search `arbitrage` -> `0` models
- Search `cross chain arbitrage` -> `0` models
- Search `wallet drain` -> `0` models
- Search `mev` -> `0` models

Existing Goldy scope is protocol-level risk and NFT wash-trading, so cross-DEX execution pressure is non-overlapping and additive.

## Selected Idea

`Cross-DEX-Arbitrage-Pressure-Index`

Reason:
- High uniqueness on hub search surface
- Strong practical value for routing and execution risk
- Can be built from open and reproducible features
- Compatible with lightweight ONNX deployment constraints
