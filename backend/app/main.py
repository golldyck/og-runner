"""FastAPI application entry point for OG Runner."""

from pathlib import Path
from time import monotonic

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.schemas import (
    AssistantRequest,
    AssistantModelsResponse,
    AssistantResponse,
    BridgeLeaderboardResponse,
    GlobalLeaderboardResponse,
    MarketContextRequest,
    MarketContextResponse,
    ModelListResponse,
    ModelSearchResponse,
    ModelResolveRequest,
    ModelResolveResponse,
    ProtocolPreviewResponse,
    RunModelRequest,
    RunModelResponse,
    WalletPreflightResponse,
)
from app.services.og_runner import (
    build_bridge_leaderboard,
    build_global_leaderboard,
    build_market_context,
    build_model_usage,
    build_protocol_proxy_html,
    fetch_protocol_preview,
    generate_assistant_answer,
    get_wallet_preflight,
    list_available_llm_models,
    list_models,
    run_demo,
    run_live,
    resolve_model,
    resolve_tee_llm_model_name,
    save_model_run,
    search_models,
    supports_live_inference,
    supports_live_llm,
)

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
)

_FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / "frontend_dist"
_FRONTEND_ASSETS_DIR = _FRONTEND_DIST_DIR / "assets"

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if _FRONTEND_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_ASSETS_DIR), name="assets")

_LIVE_INFERENCE_COOLDOWN_SECONDS = 300
_live_inference_cooldown_until = 0.0
_last_live_inference_error = ""


def _live_inference_available() -> bool:
    return supports_live_inference() and monotonic() >= _live_inference_cooldown_until


def _live_inference_cooldown_active() -> bool:
    return supports_live_inference() and monotonic() < _live_inference_cooldown_until


def _mark_live_inference_failure(exc: Exception) -> None:
    global _live_inference_cooldown_until, _last_live_inference_error
    _live_inference_cooldown_until = monotonic() + _LIVE_INFERENCE_COOLDOWN_SECONDS
    _last_live_inference_error = str(exc)


def _execute_model_run(model, payload: RunModelRequest, merged_inputs: dict):
    execution = None
    if payload.mode != "demo" and _live_inference_available():
        try:
            execution = run_live(model, merged_inputs)
        except Exception as exc:
            _mark_live_inference_failure(exc)
            execution = run_demo(model, merged_inputs)
            execution.warnings.append(f"Live OpenGradient inference failed, demo fallback used: {exc}")
    else:
        execution = run_demo(model, merged_inputs)
        if payload.mode != "demo":
            if _live_inference_cooldown_active():
                execution.warnings.append(
                    "Live OpenGradient inference is temporarily cooling down after a failed attempt. Using local fallback."
                )
            elif settings.og_private_key and not settings.og_enable_live_inference:
                execution.warnings.append(
                    "Live OpenGradient inference is currently disabled in backend settings. Using local fallback."
                )
            else:
                execution.warnings.append("Set OG_PRIVATE_KEY in backend .env to enable live OpenGradient inference.")
    return execution


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "opengradient_live_ready": _live_inference_available(),
        "opengradient_llm_ready": supports_live_llm(),
    }


@app.get("/api/wallet/preflight", response_model=WalletPreflightResponse)
async def wallet_preflight_endpoint() -> WalletPreflightResponse:
    """Return wallet readiness for OpenGradient live inference and TEE LLM flows."""
    return WalletPreflightResponse(**get_wallet_preflight())


@app.get("/api/assistant/models", response_model=AssistantModelsResponse)
async def assistant_models_endpoint() -> AssistantModelsResponse:
    """Return available OpenGradient TEE LLM models exposed by the installed SDK."""
    return AssistantModelsResponse(
        current_model=resolve_tee_llm_model_name(),
        models=list_available_llm_models(),
    )


@app.post("/api/models/resolve", response_model=ModelResolveResponse)
async def resolve_model_endpoint(payload: ModelResolveRequest) -> ModelResolveResponse:
    """Resolve a hub URL, slug, or CID into OG Runner metadata."""
    try:
        model = resolve_model(payload.model_ref)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ModelResolveResponse(model=model)


@app.get("/api/models", response_model=ModelListResponse)
async def list_models_endpoint() -> ModelListResponse:
    """Return the curated Goldy model registry."""
    return ModelListResponse(models=list_models())


@app.get("/api/models/search", response_model=ModelSearchResponse)
async def search_models_endpoint(q: str = "") -> ModelSearchResponse:
    """Search curated models by title, slug, category, or summary."""
    return ModelSearchResponse(query=q, models=search_models(q))


@app.get("/api/protocol/preview", response_model=ProtocolPreviewResponse)
async def protocol_preview_endpoint(url: str = "") -> ProtocolPreviewResponse:
    """Fetch lightweight protocol metadata and iframe embedability hints."""
    if not url.strip():
        raise HTTPException(status_code=400, detail="Protocol URL is required.")
    return ProtocolPreviewResponse(**fetch_protocol_preview(url))


@app.get("/api/protocol/render", response_class=HTMLResponse)
async def protocol_render_endpoint(url: str = "") -> HTMLResponse:
    """Return a proxied HTML document so protocol pages stay visible in the embedded viewport."""
    if not url.strip():
        raise HTTPException(status_code=400, detail="Protocol URL is required.")
    return HTMLResponse(content=build_protocol_proxy_html(url))


@app.post("/api/market/context", response_model=MarketContextResponse)
async def market_context_endpoint(payload: MarketContextRequest) -> MarketContextResponse:
    """Return live market and protocol context to enrich the current model result."""
    try:
        model = resolve_model(payload.model_ref)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    context = build_market_context(
        model=model,
        target_url=payload.target_url,
        normalized_input=payload.normalized_input,
        result=payload.result,
    )
    return MarketContextResponse(**context)


@app.get("/api/leaderboards/bridges", response_model=BridgeLeaderboardResponse)
async def bridge_leaderboard_endpoint() -> BridgeLeaderboardResponse:
    """Return a bridge leaderboard for the bridge risk model."""
    model = resolve_model("cross-chain-bridge-risk-classifier")
    return BridgeLeaderboardResponse(model=model, entries=build_bridge_leaderboard())


@app.get("/api/leaderboards/global", response_model=GlobalLeaderboardResponse)
async def global_leaderboard_endpoint() -> GlobalLeaderboardResponse:
    """Return recent user runs across all models and aggregate model usage."""
    return GlobalLeaderboardResponse(
        entries=build_global_leaderboard(),
        model_usage=build_model_usage(),
    )


@app.post("/api/models/run", response_model=RunModelResponse)
async def run_model_endpoint(payload: RunModelRequest) -> RunModelResponse:
    """Run a prototype inference flow for a supported Goldy model."""
    try:
        model = resolve_model(payload.model_ref)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    merged_inputs = dict(payload.inputs)
    if payload.target_url:
        merged_inputs["target_url"] = payload.target_url

    if payload.mode == "demo":
        merged_inputs = model.sample_input

    execution = _execute_model_run(model, payload, merged_inputs)

    save_model_run(
        model=model,
        normalized_input=execution.normalized_input,
        result=execution.result,
        target_url=payload.target_url,
        compare_url=payload.compare_url,
    )

    comparison: list[RunModelResponse] = []
    if payload.compare_url:
        compare_inputs = dict(payload.inputs)
        compare_inputs["target_url"] = payload.compare_url
        compare_execution = _execute_model_run(model, payload, compare_inputs)
        comparison.append(
            RunModelResponse(
                model=model,
                normalized_input=compare_execution.normalized_input,
                result=compare_execution.result,
                ai_explanation=compare_execution.ai_explanation,
                execution_mode=compare_execution.execution_mode,
                transaction_hash=compare_execution.transaction_hash,
                warnings=compare_execution.warnings,
                comparison=[],
            )
        )

    return RunModelResponse(
        model=model,
        normalized_input=execution.normalized_input,
        result=execution.result,
        ai_explanation=execution.ai_explanation,
        execution_mode=execution.execution_mode,
        transaction_hash=execution.transaction_hash,
        warnings=execution.warnings,
        comparison=comparison,
    )


@app.post("/api/assistant", response_model=AssistantResponse)
async def assistant_endpoint(payload: AssistantRequest) -> AssistantResponse:
    """Explain a model, result, or model search request using OpenGradient LLM when configured."""
    model = None
    if payload.model_ref:
        try:
            model = resolve_model(payload.model_ref)
        except KeyError:
            model = None

    answer, source, model_used = generate_assistant_answer(
        message=payload.message,
        model=model,
        result=payload.result,
        target_url=payload.target_url,
        llm_model=payload.llm_model,
    )
    return AssistantResponse(answer=answer, source=source, model_used=model_used)


@app.get("/{full_path:path}")
async def frontend_app(full_path: str):
    """Serve the built frontend for Railway single-service deploys."""
    if not _FRONTEND_DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend build is not available.")

    requested = (_FRONTEND_DIST_DIR / full_path).resolve()
    try:
        requested.relative_to(_FRONTEND_DIST_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found.") from exc

    if full_path and requested.is_file():
        return FileResponse(requested)

    index_path = _FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend index is not available.")
    return FileResponse(index_path)
