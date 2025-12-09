"""Utility functions for Kalibr SDK.

Helper functions for:
- Environment configuration
- Event validation
- JSON serialization
- Logging
"""

import json
import os
from datetime import date, datetime, time
from typing import Any, Dict, Optional


def load_config_from_env() -> Dict[str, str]:
    """Load Kalibr configuration from environment variables.

    Returns:
        Configuration dict with keys:
        - clickhouse_url: ClickHouse connection URL
        - project_name: Project/service name
        - auth_token: API authentication token
        - environment: Environment (prod/staging/dev)
        - tenant_id: Tenant identifier
        - workflow_id: Workflow identifier
        - sandbox_id: Sandbox/VM identifier
        - runtime_env: Runtime environment
        - collector_url: Collector endpoint URL
    """
    config = {
        "clickhouse_url": os.getenv("CLICKHOUSE_URL", "http://localhost:8123"),
        "project_name": os.getenv("KALIBR_PROJECT_NAME", "kalibr-app"),
        "auth_token": os.getenv("KALIBR_AUTH_TOKEN", ""),
        "api_key": os.getenv("KALIBR_API_KEY", ""),
        "environment": os.getenv("KALIBR_ENVIRONMENT", "prod"),
        "tenant_id": os.getenv("KALIBR_TENANT_ID", "default"),
        "workflow_id": os.getenv("KALIBR_WORKFLOW_ID", "default-workflow"),
        "sandbox_id": os.getenv("SANDBOX_ID", "local"),
        "runtime_env": os.getenv("RUNTIME_ENV", "local"),
        "api_endpoint": os.getenv("KALIBR_API_ENDPOINT", "https://api.kalibr.systems/api/v1/traces"),
        "collector_url": os.getenv("KALIBR_COLLECTOR_URL", "https://api.kalibr.systems/api/ingest"),
    }
    return config


def validate_event(event: Dict[str, Any]) -> bool:
    """Validate that event has required fields.

    Args:
        event: Event dictionary

    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "trace_id",
        "span_id",
        "timestamp",
        "service",
        "vendor",
        "operation",
        "latency_ms",
        "status",
    ]

    for field in required_fields:
        if field not in event:
            return False

    return True


def serialize_event(event: Dict[str, Any]) -> str:
    """Serialize event to JSON string.

    Handles special types like datetime, date, time.

    Args:
        event: Event dictionary

    Returns:
        JSON string
    """

    def default_handler(obj):
        """Handle non-serializable types."""
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(event, default=default_handler)


def safe_get_nested(data: Dict, keys: list, default: Any = None) -> Any:
    """Safely get nested dictionary value.

    Args:
        data: Dictionary to query
        keys: List of nested keys
        default: Default value if key path doesn't exist

    Returns:
        Value at nested key path, or default

    Example:
        >>> data = {"a": {"b": {"c": 123}}}
        >>> safe_get_nested(data, ["a", "b", "c"])
        123
        >>> safe_get_nested(data, ["a", "x", "y"], default=0)
        0
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def truncate_string(s: str, max_length: int = 1000) -> str:
    """Truncate string to max length with ellipsis.

    Args:
        s: String to truncate
        max_length: Maximum length

    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[: max_length - 3] + "..."


def format_cost(cost_usd: float) -> str:
    """Format cost in USD for display.

    Args:
        cost_usd: Cost in USD

    Returns:
        Formatted string (e.g., "$0.0123")
    """
    if cost_usd < 0.0001:
        return "$0.0000"
    elif cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    elif cost_usd < 1.0:
        return f"${cost_usd:.3f}"
    else:
        return f"${cost_usd:.2f}"


def format_latency(latency_ms: int) -> str:
    """Format latency for display.

    Args:
        latency_ms: Latency in milliseconds

    Returns:
        Formatted string (e.g., "420ms" or "2.3s")
    """
    if latency_ms < 1000:
        return f"{latency_ms}ms"
    else:
        seconds = latency_ms / 1000
        return f"{seconds:.1f}s"


def get_log_prefix() -> str:
    """Get log prefix for Kalibr SDK messages.

    Returns:
        Log prefix string
    """
    return "[Kalibr SDK]"


def log_info(message: str):
    """Log info message."""
    print(f"{get_log_prefix()} ℹ️  {message}")


def log_warning(message: str):
    """Log warning message."""
    print(f"{get_log_prefix()} ⚠️  {message}")


def log_error(message: str):
    """Log error message."""
    print(f"{get_log_prefix()} ❌ {message}")


def log_success(message: str):
    """Log success message."""
    print(f"{get_log_prefix()} ✅ {message}")
