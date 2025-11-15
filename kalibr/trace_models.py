"""
Unified Trace Event Models - Generated from trace_event_schema.json v1.0.0

This module provides Pydantic models for trace events that are shared
between the SDK and backend to ensure schema consistency.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TraceEvent(BaseModel):
    """
    Unified trace event model for LLM observability.

    Compatible with:
    - Kalibr SDK v1.0.30+
    - Kalibr Backend v1.0+
    - ClickHouse storage schema

    Phase 4.5: Strict validation enabled to enforce data quality.
    """

    model_config = ConfigDict(
        # Phase 4.5: Relaxed strict mode to allow type coercion (str -> datetime)
        # but keep extra='forbid' to reject unknown fields
        extra="forbid",  # Reject unknown fields - this is the key validation
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "schema_version": "1.0",
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                "span_id": "a1b2c3d4-e5f6-47a8-b9c0-123456789abc",
                "parent_span_id": None,
                "tenant_id": "acme-corp",
                "provider": "openai",
                "model_id": "gpt-4o",
                "operation": "chat_completion",
                "duration_ms": 250,
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.000375,
                "status": "success",
                "timestamp": "2025-10-30T12:00:00.000Z",
            }
        },
    )

    # Schema metadata
    schema_version: Literal["1.0"] = Field(description="Schema version (1.0)")

    # Identity
    trace_id: str = Field(
        min_length=16,
        max_length=36,
        description="Unique trace identifier (UUID or 16-char alphanumeric)",
    )
    span_id: str = Field(
        min_length=16,
        max_length=36,
        description="Unique span identifier (UUIDv4 format)"
    )
    parent_span_id: Optional[str] = Field(
        None,
        min_length=16,
        max_length=36,
        description="Parent span ID for nested operations (UUIDv4 format)"
    )

    # Tenant & Context
    tenant_id: str = Field(min_length=1, max_length=64, description="Tenant identifier")
    workflow_id: Optional[str] = Field(
        None, max_length=64, description="Workflow identifier for multi-step operations"
    )
    sandbox_id: Optional[str] = Field(
        None, max_length=64, description="Sandbox/VM/Environment identifier"
    )
    runtime_env: Optional[str] = Field(
        None, max_length=32, description="Runtime environment (vercel_vm, fly_io, local, etc.)"
    )

    # LLM Details
    provider: Literal["openai", "anthropic", "google", "cohere", "custom"] = Field(
        description="LLM provider"
    )
    model_id: str = Field(
        min_length=1, max_length=64, description="Model identifier (e.g., gpt-4o, claude-3-opus)"
    )
    model_name: Optional[str] = Field(
        None, description="Human-readable model name (optional, defaults to model_id)"
    )

    # Operation
    operation: str = Field(
        min_length=1,
        max_length=64,
        description="Operation type (e.g., chat_completion, summarize, refine)",
    )
    endpoint: Optional[str] = Field(
        None, max_length=128, description="API endpoint or function name"
    )

    # Performance
    duration_ms: int = Field(ge=0, description="Total duration in milliseconds")
    latency_ms: Optional[int] = Field(None, description="Legacy field, same as duration_ms")

    # Tokens
    input_tokens: int = Field(ge=0, description="Number of input tokens")
    output_tokens: int = Field(ge=0, description="Number of output tokens")
    total_tokens: Optional[int] = Field(
        None, description="Total tokens (input + output), computed if not provided"
    )

    # Cost
    cost_usd: float = Field(ge=0.0, description="Total cost in USD")
    total_cost_usd: Optional[float] = Field(None, description="Legacy field, same as cost_usd")
    unit_price_usd: Optional[float] = Field(None, ge=0.0, description="Price per token in USD")

    # Status & Errors
    status: Literal["success", "error", "timeout"] = Field(description="Execution status")
    error_type: Optional[str] = Field(
        None, max_length=64, description="Error class name if status is error"
    )
    error_message: Optional[str] = Field(
        None, max_length=512, description="Error message if status is error"
    )
    stack_trace: Optional[str] = Field(None, description="Stack trace for errors (optional)")

    # Timestamps
    timestamp: datetime = Field(description="Event timestamp (ISO 8601 UTC)")
    ts_start: Optional[datetime] = Field(None, description="Operation start time (ISO 8601 UTC)")
    ts_end: Optional[datetime] = Field(None, description="Operation end time (ISO 8601 UTC)")

    # Environment
    environment: Optional[Literal["prod", "staging", "dev"]] = Field(
        None, description="Deployment environment"
    )
    service: Optional[str] = Field(None, max_length=64, description="Service name")

    # User Context
    user_id: Optional[str] = Field(
        None, max_length=64, description="End user identifier (anonymized)"
    )
    request_id: Optional[str] = Field(
        None, max_length=64, description="Request identifier for correlation"
    )

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional custom metadata")
    data_class: Optional[Literal["economic", "performance", "diagnostic"]] = Field(
        None, description="Data classification"
    )

    # Legacy fields
    vendor: Optional[str] = Field(None, description="Legacy field, same as provider")

    @field_validator("total_tokens", mode="before")
    @classmethod
    def compute_total_tokens(cls, v, info):
        """Auto-compute total_tokens if not provided."""
        if v is None and "input_tokens" in info.data and "output_tokens" in info.data:
            return info.data["input_tokens"] + info.data["output_tokens"]
        return v

    @field_validator("model_name", mode="before")
    @classmethod
    def default_model_name(cls, v, info):
        """Default model_name to model_id if not provided."""
        if v is None and "model_id" in info.data:
            return info.data["model_id"]
        return v

    @field_validator("latency_ms", mode="before")
    @classmethod
    def sync_latency(cls, v, info):
        """Sync latency_ms with duration_ms if not provided."""
        if v is None and "duration_ms" in info.data:
            return info.data["duration_ms"]
        return v

    @field_validator("total_cost_usd", mode="before")
    @classmethod
    def sync_cost(cls, v, info):
        """Sync total_cost_usd with cost_usd if not provided."""
        if v is None and "cost_usd" in info.data:
            return info.data["cost_usd"]
        return v

    @field_validator("vendor", mode="before")
    @classmethod
    def sync_vendor(cls, v, info):
        """Sync vendor with provider if not provided."""
        if v is None and "provider" in info.data:
            return info.data["provider"]
        return v


# Convenience type aliases
TraceEventDict = Dict[str, Any]
