"""Pydantic schemas for OG Runner model resolution and execution."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelResolveRequest(BaseModel):
    model_ref: str = Field(..., min_length=3)


class InputField(BaseModel):
    key: str
    label: str
    kind: Literal["number", "boolean", "text"]
    description: str
    placeholder: str | None = None


class ModelGuide(BaseModel):
    what_it_does: str
    what_you_need: list[str]
    what_result_means: list[str]
    next_steps: list[str]


class ModelDefinition(BaseModel):
    slug: str
    title: str
    owner: str
    hub_url: str
    model_cid: str
    category: str
    summary: str
    input_key: str
    input_shape: str
    result_keys: list[str]
    input_fields: list[InputField]
    sample_input: dict[str, Any]
    guide: ModelGuide
    source: Literal["curated", "hub_dynamic"] = "curated"
    schema_confidence: Literal["high", "medium", "low"] = "high"
    detected_task_type: str | None = None


class ModelResolveResponse(BaseModel):
    model: ModelDefinition


class ModelListResponse(BaseModel):
    models: list[ModelDefinition]


class ModelSearchResponse(BaseModel):
    query: str
    models: list[ModelDefinition]


class LeaderboardEntry(BaseModel):
    rank: int
    source: Literal["curated", "user"]
    model_slug: str | None = None
    model_title: str | None = None
    model_category: str | None = None
    name: str
    protocol_url: str
    summary: str
    created_at: str | None = None
    headline_score: str | None = None
    headline_label: str | None = None
    normalized_input: dict[str, Any]
    result: dict[str, Any]


class BridgeLeaderboardResponse(BaseModel):
    model: ModelDefinition
    entries: list[LeaderboardEntry]


class ModelUsageStat(BaseModel):
    model_slug: str
    model_title: str
    runs: int


class GlobalLeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    model_usage: list[ModelUsageStat]


class RunModelRequest(BaseModel):
    model_ref: str
    mode: Literal["manual", "demo", "url"] = "manual"
    target_url: str | None = None
    compare_url: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)


class RunModelResponse(BaseModel):
    model: ModelDefinition
    normalized_input: dict[str, Any]
    result: dict[str, Any]
    ai_explanation: str
    execution_mode: Literal["live", "demo"]
    transaction_hash: str | None = None
    warnings: list[str] = Field(default_factory=list)
    comparison: list["RunModelResponse"] = Field(default_factory=list)


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=3)
    model_ref: str | None = None
    llm_model: str | None = None
    target_url: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    answer: str
    source: Literal["opengradient_llm", "local_fallback"]
    model_used: str | None = None


class AssistantModelsResponse(BaseModel):
    current_model: str
    models: list[str]


class WalletPreflightResponse(BaseModel):
    wallet_address: str | None = None
    base_sepolia_eth: float | None = None
    opg_balance: float | None = None
    permit2_allowance: float | None = None
    llm_ready: bool
    live_inference_ready: bool
    issues: list[str] = Field(default_factory=list)


class ProtocolPreviewResponse(BaseModel):
    url: str
    host: str
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    site_name: str | None = None
    embed_allowed: bool
    status_code: int | None = None
