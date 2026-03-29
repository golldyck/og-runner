# OG Runner

OG Runner is a standalone site for running OpenGradient models from the Hub.

Current flow:
- paste OpenGradient model URL, slug, or CID
- get an AI guide for how to use the model
- test the model with demo, manual, or URL-assisted input
- view the result, breakdown, and execution mode

Run locally:

```bash
cd /Users/admin/og-runner/backend
source .venv311/bin/activate
uvicorn app.main:app --reload
```

```bash
cd /Users/admin/og-runner/frontend
npm run dev
```

Current backend endpoints:
- `POST /api/models/resolve`
- `POST /api/models/run`
- `GET /health`

Live OpenGradient inference:
- add `OG_PRIVATE_KEY` to [backend/.env](/Users/admin/og-runner/backend/.env)
- without it, OG Runner runs in safe demo fallback mode
