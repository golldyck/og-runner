# OG Runner

OG Runner is a local product shell for testing curated OpenGradient model flows against protocol URLs, manual inputs, and demo data.

It currently includes:

- a FastAPI backend for model resolution, execution, heuristics, and leaderboards
- a React frontend for running models and inspecting results
- curated Goldy model packs, including `DEX Liquidity Exit Risk Scorer`

## Included Models

- `Governance Capture Risk Scorer`
- `Cross-Chain Bridge Risk Classifier`
- `DeFi Protocol Health Score`
- `Stablecoin Depeg Risk Monitor`
- `NFT Wash Trading Detector`
- `DEX Liquidity Exit Risk Scorer`

## Core Features

- resolve a model from a slug, hub URL, or CID-style reference
- run demo or live-style flows against a protocol URL
- show score, verdict, explanation, and parameter scales
- save user runs into global and bridge leaderboards
- package new model concepts under `model-packs/`

## Project Structure

```text
og-runner/
├── backend/       # FastAPI API, model registry, heuristics, run storage
├── frontend/      # React + Vite product UI
└── model-packs/   # model docs, metadata, ONNX artifacts
```

## Local Development

### 1. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Backend runs on `http://127.0.0.1:8000`.

### 2. Start the frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Frontend runs on `http://127.0.0.1:5173`.

## Environment

### Backend

See [backend/.env.example](/Users/admin/og-runner/backend/.env.example).

- `OG_PRIVATE_KEY`: enables live OpenGradient inference
- `OG_RPC_URL`: OpenGradient EVM RPC
- `OG_API_URL`: OpenGradient SDK API
- `OG_INFERENCE_CONTRACT_ADDRESS`: inference contract

Without `OG_PRIVATE_KEY`, OG Runner uses demo fallback mode.

### Frontend

See [frontend/.env.example](/Users/admin/og-runner/frontend/.env.example).

- `VITE_API_BASE_URL`: backend base URL

## API Endpoints

- `GET /health`
- `GET /api/models`
- `POST /api/models/resolve`
- `POST /api/models/run`
- `GET /api/leaderboards/global`
- `GET /api/leaderboards/bridges`

## Model Packs

The first packaged custom model lives in [model-packs/dex-liquidity-exit-risk-scorer](/Users/admin/og-runner/model-packs/dex-liquidity-exit-risk-scorer).

It includes:

- product README
- metadata
- release notes
- ONNX builder
- generated ONNX artifact
- final handoff report

## Verification

Frontend:

```bash
cd frontend
npm run build
npm run lint
```

Backend:

```bash
python3 -m compileall backend/app
```

## Repository

- GitHub: `git@github.com:golldyck/og-runner.git`
- Visibility: private

## License

MIT. See [LICENSE](/Users/admin/og-runner/LICENSE).
