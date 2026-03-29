# OG Runner Frontend

React + TypeScript + Vite frontend for OG Runner.

## Scripts

```bash
npm run dev
npm run build
npm run lint
npm run preview
```

## Environment

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Default value:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Notes

- the UI is designed around curated OpenGradient model flows
- result rendering is model-aware and shows score, summary, and parameter scales
- the frontend expects the FastAPI backend to be running locally
