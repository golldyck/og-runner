"""FastAPI application entry point for OG Runner."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.schemas import (
    BridgeLeaderboardResponse,
    GlobalLeaderboardResponse,
    ModelListResponse,
    ModelResolveRequest,
    ModelResolveResponse,
    RunModelRequest,
    RunModelResponse,
)
from app.services.og_runner import (
    build_bridge_leaderboard,
    build_global_leaderboard,
    build_model_usage,
    list_models,
    run_demo,
    run_live,
    resolve_model,
    save_model_run,
    supports_live_inference,
)

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _execute_model_run(model, payload: RunModelRequest, merged_inputs: dict):
    execution = None
    if payload.mode != "demo" and supports_live_inference():
        try:
            execution = run_live(model, merged_inputs)
        except Exception as exc:
            execution = run_demo(model, merged_inputs)
            execution.warnings.append(f"Live OpenGradient inference failed, demo fallback used: {exc}")
    else:
        execution = run_demo(model, merged_inputs)
        if payload.mode != "demo":
            execution.warnings.append("Set OG_PRIVATE_KEY in backend .env to enable live OpenGradient inference.")
    return execution


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "opengradient_live_ready": supports_live_inference(),
    }


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
