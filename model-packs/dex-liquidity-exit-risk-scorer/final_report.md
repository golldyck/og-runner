# Final Report

## Task Outcome

Created a new model pack for **DEX Liquidity Exit Risk Scorer** and integrated it into OG Runner as a first-class model across backend shaping and frontend rendering.

## Why This Model Was Chosen

The current Goldy model set in this project already covers:

1. Governance capture risk
2. Cross-chain bridge risk
3. DeFi protocol health
4. Stablecoin depeg risk
5. NFT wash trading

The missing product gap was a DEX-specific model for **liquidity durability under LP exits, concentration, incentive decay, and flow stress**.

## Artifacts Created

- `README.md`
- `model_metadata.json`
- `release_notes.md`
- `idea_report.md`
- `build_onnx.js`
- `dex-liquidity-exit-risk-scorer.onnx`

## OG Runner Integration

The model is now wired into:

- backend model registry
- URL-to-input inference
- result shaping and explanation
- frontend score rendering
- frontend parameter scales
- frontend model guidance and CTA labels

## Verification

- `python3 -m compileall backend/app` passed
- `npm run build` passed
- `npm run lint` passed
- ONNX artifact generated successfully

## Hub Limitation

Direct autonomous inspection of `hub.opengradient.ai` was blocked from this environment by a CloudFront `403`, so full live Hub research and direct publication could not be completed here.

## Next Manual Step

Open the Hub in your normal signed-in browser session and upload this pack:

- README
- metadata
- ONNX file
- release notes

Then replace the temporary local CID placeholder with the real published model CID.
