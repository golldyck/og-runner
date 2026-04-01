# Contributing to OG Runner

Thanks for contributing to OG Runner.

This repository is a product-facing OpenGradient runner, so changes should improve one of these areas:

- model resolution and execution reliability
- frontend clarity and operator workflow
- protocol extraction and contextual analysis
- deployment stability and production readiness
- model-pack quality and documentation

## Development setup

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Full stack:

```bash
cp .env.example .env
docker compose up --build
```

## Before opening a pull request

Run the checks that match your change:

```bash
cd frontend
npm run lint
npm run build
```

```bash
python3 -m compileall backend/app
```

```bash
docker compose build
```

## Pull request guidelines

- Keep PRs focused. Separate frontend polish, backend execution changes, and model-pack additions when possible.
- Describe the user-visible effect of the change, not only the code diff.
- If you change scoring logic or fallback behavior, explain the tradeoff and expected result shape.
- If you add a model pack, include metadata, docs, artifact generation path, and release notes.
- If you change deployment behavior, include the exact env vars or infrastructure assumptions.

## Model-pack contributions

New model packs should include:

- `README.md`
- `model_metadata.json`
- `release_notes.md`
- builder or generation script when applicable
- produced artifact when the pack is intended to run locally
- a short explanation of expected inputs and outputs

## Reporting issues

Use GitHub Issues for:

- reproducible bugs
- UX regressions
- deployment problems
- model-pack requests
- documentation gaps

For security-sensitive issues, do not open a public issue. Follow the process in `SECURITY.md`.
