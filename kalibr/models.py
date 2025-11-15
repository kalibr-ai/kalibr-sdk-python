"""Data models for Kalibr SDK."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class TraceConfig:
    """Configuration for tracing."""

    operation: str = "model_call"
    endpoint: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    environment: str = "prod"


@dataclass
class EventData:
    """Event data structure."""

    schema_version: str = "1.0"
    trace_id: str = ""
    span_id: str = ""
    parent_id: Optional[str] = None
    tenant_id: str = ""
    environment: str = "prod"
    ts_start: Optional[datetime] = None
    ts_end: Optional[datetime] = None
    endpoint: str = ""
    operation: str = "model_call"
    provider: str = "unknown"
    model_id: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    status: str = "200"
    prompt_hash: str = ""
    response_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
