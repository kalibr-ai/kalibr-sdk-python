"""
Kalibr Trace Capsule - Portable JSON payload for cross-MCP trace propagation.

A capsule carries observability context across agent hops, maintaining a rolling
window of recent operations and aggregate metrics.

Usage:
    from kalibr.trace_capsule import TraceCapsule

    # Create new capsule
    capsule = TraceCapsule()

    # Append hop
    capsule.append_hop({
        "provider": "openai",
        "operation": "summarize",
        "model": "gpt-4o",
        "duration_ms": 1200,
        "status": "success",
        "cost_usd": 0.005
    })

    # Serialize for HTTP header
    header_value = capsule.to_json()

    # Deserialize from header
    received_capsule = TraceCapsule.from_json(header_value)
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class TraceCapsule:
    """Portable JSON payload containing rolling trace history.

    Attributes:
        trace_id: Unique identifier for the trace chain
        timestamp: ISO 8601 timestamp of last update
        aggregate_cost_usd: Cumulative cost across all hops
        aggregate_latency_ms: Cumulative latency across all hops
        last_n_hops: Rolling window of last N hops (max 5)
        tenant_id: Optional tenant identifier
        workflow_id: Optional workflow identifier
        metadata: Optional custom metadata
    """

    MAX_HOPS = 5  # Keep payload compact for HTTP headers

    def __init__(
        self,
        trace_id: Optional[str] = None,
        last_n_hops: Optional[List[Dict[str, Any]]] = None,
        aggregate_cost_usd: float = 0.0,
        aggregate_latency_ms: float = 0.0,
        tenant_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context_token: Optional[str] = None,
        parent_context_token: Optional[str] = None,
    ):
        """Initialize a new TraceCapsule.

        Args:
            trace_id: Unique trace identifier (generates UUID if not provided)
            last_n_hops: Existing hop history
            aggregate_cost_usd: Starting cumulative cost
            aggregate_latency_ms: Starting cumulative latency
            tenant_id: Tenant identifier
            workflow_id: Workflow identifier
            metadata: Custom metadata
            context_token: Context token for this runtime session (Phase 3C)
            parent_context_token: Parent runtime's context token (Phase 3C)
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.aggregate_cost_usd = aggregate_cost_usd
        self.aggregate_latency_ms = aggregate_latency_ms
        self.last_n_hops: List[Dict[str, Any]] = last_n_hops or []
        self.tenant_id = tenant_id
        self.workflow_id = workflow_id
        self.metadata = metadata or {}
        # Phase 3C: Context token propagation (keep as UUID for consistency)
        self.context_token = context_token or str(uuid.uuid4())
        self.parent_context_token = parent_context_token

    def append_hop(self, hop: Dict[str, Any]) -> None:
        """Append a new hop to the capsule.

        Maintains a rolling window of last N hops to keep payload compact.
        Updates aggregate metrics automatically.

        Args:
            hop: Dictionary containing hop metadata
                Required fields: provider, operation, status
                Optional fields: model, duration_ms, cost_usd, input_tokens,
                                output_tokens, error_type, agent_name

        Example:
            capsule.append_hop({
                "provider": "openai",
                "operation": "chat_completion",
                "model": "gpt-4o",
                "duration_ms": 1200,
                "status": "success",
                "cost_usd": 0.005,
                "input_tokens": 150,
                "output_tokens": 75,
                "agent_name": "code-writer"
            })
        """
        # Add hop_index
        hop["hop_index"] = len(self.last_n_hops)

        # Append to history
        self.last_n_hops.append(hop)

        # Maintain rolling window (keep last N hops)
        if len(self.last_n_hops) > self.MAX_HOPS:
            self.last_n_hops.pop(0)

        # Update aggregates
        self.aggregate_cost_usd += hop.get("cost_usd", 0.0)
        self.aggregate_latency_ms += hop.get("duration_ms", 0.0)

        # Update timestamp
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def get_last_hop(self) -> Optional[Dict[str, Any]]:
        """Get the most recent hop.

        Returns:
            Last hop dictionary or None if no hops exist
        """
        return self.last_n_hops[-1] if self.last_n_hops else None

    def get_hop_count(self) -> int:
        """Get total number of hops in capsule.

        Returns:
            Number of hops in the rolling window
        """
        return len(self.last_n_hops)

    def to_json(self) -> str:
        """Serialize capsule to JSON string for HTTP header transmission.

        Returns:
            Compact JSON string representation
        """
        data = {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "aggregate_cost_usd": round(self.aggregate_cost_usd, 6),
            "aggregate_latency_ms": round(self.aggregate_latency_ms, 2),
            "last_n_hops": self.last_n_hops,
        }

        # Add optional fields only if present
        if self.tenant_id:
            data["tenant_id"] = self.tenant_id
        if self.workflow_id:
            data["workflow_id"] = self.workflow_id
        if self.metadata:
            data["metadata"] = self.metadata

        # Phase 3C: Include context tokens
        if self.context_token:
            data["context_token"] = self.context_token
        if self.parent_context_token:
            data["parent_context_token"] = self.parent_context_token

        return json.dumps(data, separators=(",", ":"))  # Compact JSON

    def to_dict(self) -> Dict[str, Any]:
        """Convert capsule to dictionary.

        Returns:
            Dictionary representation of capsule
        """
        data = {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "aggregate_cost_usd": self.aggregate_cost_usd,
            "aggregate_latency_ms": self.aggregate_latency_ms,
            "last_n_hops": self.last_n_hops,
        }

        if self.tenant_id:
            data["tenant_id"] = self.tenant_id
        if self.workflow_id:
            data["workflow_id"] = self.workflow_id
        if self.metadata:
            data["metadata"] = self.metadata

        # Phase 3C: Include context tokens
        if self.context_token:
            data["context_token"] = self.context_token
        if self.parent_context_token:
            data["parent_context_token"] = self.parent_context_token

        return data

    @classmethod
    def from_json(cls, s: str) -> "TraceCapsule":
        """Deserialize capsule from JSON string.

        Args:
            s: JSON string from HTTP header

        Returns:
            TraceCapsule instance

        Raises:
            json.JSONDecodeError: If JSON is invalid
            KeyError: If required fields are missing
        """
        try:
            data = json.loads(s)
            return cls(
                trace_id=data.get("trace_id"),
                last_n_hops=data.get("last_n_hops", []),
                aggregate_cost_usd=data.get("aggregate_cost_usd", 0.0),
                aggregate_latency_ms=data.get("aggregate_latency_ms", 0.0),
                tenant_id=data.get("tenant_id"),
                workflow_id=data.get("workflow_id"),
                metadata=data.get("metadata"),
                # Phase 3C: Context token propagation
                context_token=data.get("context_token"),
                parent_context_token=data.get("parent_context_token"),
            )
        except json.JSONDecodeError as e:
            # Return empty capsule if parsing fails (graceful degradation)
            print(f"⚠️ Failed to parse TraceCapsule: {e}")
            return cls()
        except Exception as e:
            print(f"⚠️ Error creating TraceCapsule: {e}")
            return cls()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceCapsule":
        """Create capsule from dictionary.

        Args:
            data: Dictionary containing capsule data

        Returns:
            TraceCapsule instance
        """
        return cls(
            trace_id=data.get("trace_id"),
            last_n_hops=data.get("last_n_hops", []),
            aggregate_cost_usd=data.get("aggregate_cost_usd", 0.0),
            aggregate_latency_ms=data.get("aggregate_latency_ms", 0.0),
            tenant_id=data.get("tenant_id"),
            workflow_id=data.get("workflow_id"),
            metadata=data.get("metadata"),
        )

    def __repr__(self) -> str:
        """String representation of capsule."""
        return (
            f"TraceCapsule(trace_id={self.trace_id}, "
            f"hops={len(self.last_n_hops)}, "
            f"cost=${self.aggregate_cost_usd:.6f}, "
            f"latency={self.aggregate_latency_ms:.2f}ms)"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        hops_summary = ", ".join(
            [f"{hop.get('provider', '?')}/{hop.get('operation', '?')}" for hop in self.last_n_hops]
        )
        return (
            f"TraceCapsule[{self.trace_id}]: "
            f"{len(self.last_n_hops)} hops ({hops_summary}), "
            f"${self.aggregate_cost_usd:.4f}, "
            f"{self.aggregate_latency_ms:.0f}ms"
        )


# Convenience function for FastAPI integration
def get_or_create_capsule(header_value: Optional[str] = None) -> TraceCapsule:
    """Get existing capsule from header or create new one.

    Args:
        header_value: Value of X-Kalibr-Capsule header

    Returns:
        TraceCapsule instance
    """
    if header_value:
        return TraceCapsule.from_json(header_value)
    return TraceCapsule()
