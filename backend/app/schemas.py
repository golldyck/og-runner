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


class ModelResolveResponse(BaseModel):
    model: ModelDefinition


class ModelListResponse(BaseModel):
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
