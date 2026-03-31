## Cross DEX Arbitrage Pressure Index v1.00

- Initial ONNX release for cross-venue arbitrage pressure scoring.
- Added 20-feature input schema covering spread persistence, execution friction, liquidity fragmentation, flow imbalance, and resilience context.
- Output tensor: `arbitrage_pressure_score` with shape `[1,1]`.
- Includes score grading and operational flags in the model documentation.
