"""Kalibr Intelligence Client - Query execution intelligence and report outcomes.

This module enables the outcome-conditioned routing loop:
1. Before executing: query get_policy() to get the best path for your goal
2. After executing: call report_outcome() to teach Kalibr what worked

Example - Policy-based routing:
    from kalibr import get_policy, report_outcome

    # Before executing - get best path
    policy = get_policy(goal="book_meeting")
    model = policy["recommended_model"]  # Use this model

    # After executing - report what happened
    report_outcome(
        trace_id=trace_id,
        goal="book_meeting",
        success=True
    )

Example - Path registration and intelligent routing:
    from kalibr import register_path, decide

    # Register paths for a goal
    register_path(goal="book_meeting", model_id="gpt-4", tool_id="calendar_tool")
    register_path(goal="book_meeting", model_id="claude-3-opus")

    # Get intelligent routing decision
    decision = decide(goal="book_meeting")
    model = decision["model_id"]  # Selected based on outcomes
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

# Default intelligence API endpoint
DEFAULT_INTELLIGENCE_URL = "https://kalibr-intelligence.fly.dev"


class KalibrIntelligence:
    """Client for Kalibr Intelligence API.

    Provides methods to query execution policies and report outcomes
    for the outcome-conditioned routing loop.

    Args:
        api_key: Kalibr API key (or set KALIBR_API_KEY env var)
        tenant_id: Tenant identifier (or set KALIBR_TENANT_ID env var)
        base_url: Intelligence API base URL (or set KALIBR_INTELLIGENCE_URL env var)
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        api_key: str | None = None,
        tenant_id: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
    ):
        self.api_key = api_key or os.getenv("KALIBR_API_KEY", "")
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "")
        self.base_url = (
            base_url
            or os.getenv("KALIBR_INTELLIGENCE_URL", DEFAULT_INTELLIGENCE_URL)
        ).rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Make authenticated request to intelligence API."""
        headers = {
            "X-API-Key": self.api_key,
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{path}"
        response = self._client.request(method, url, json=json, params=params, headers=headers)
        response.raise_for_status()
        return response

    def get_policy(
        self,
        goal: str,
        task_type: str | None = None,
        constraints: dict | None = None,
        window_hours: int = 168,
    ) -> dict[str, Any]:
        """Get execution policy for a goal.

        Returns the historically best-performing path for achieving
        the specified goal, based on outcome data.

        Args:
            goal: The goal to optimize for (e.g., "book_meeting", "resolve_ticket")
            task_type: Optional task type filter (e.g., "code", "summarize")
            constraints: Optional constraints dict with keys:
                - max_cost_usd: Maximum cost per request
                - max_latency_ms: Maximum latency
                - min_quality: Minimum quality score (0-1)
                - min_confidence: Minimum statistical confidence (0-1)
                - max_risk: Maximum risk score (0-1)
            window_hours: Time window for pattern analysis (default 1 week)

        Returns:
            dict with:
                - goal: The goal queried
                - recommended_model: Best model for this goal
                - recommended_provider: Provider for the recommended model
                - outcome_success_rate: Historical success rate (0-1)
                - outcome_sample_count: Number of outcomes in the data
                - confidence: Statistical confidence in recommendation
                - risk_score: Risk score (lower is better)
                - reasoning: Human-readable explanation
                - alternatives: List of alternative models

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            policy = intelligence.get_policy(goal="book_meeting")
            print(f"Use {policy['recommended_model']} - {policy['outcome_success_rate']:.0%} success rate")
        """
        response = self._request(
            "POST",
            "/api/v1/intelligence/policy",
            json={
                "goal": goal,
                "task_type": task_type,
                "constraints": constraints,
                "window_hours": window_hours,
            },
        )
        return response.json()

    def report_outcome(
        self,
        trace_id: str,
        goal: str,
        success: bool,
        score: float | None = None,
        failure_reason: str | None = None,
        metadata: dict | None = None,
        tool_id: str | None = None,
        execution_params: dict | None = None,
    ) -> dict[str, Any]:
        """Report execution outcome for a goal.

        This is the feedback loop that teaches Kalibr what works.
        Call this after your agent completes (or fails) a task.

        Args:
            trace_id: The trace ID from the execution
            goal: The goal this execution was trying to achieve
            success: Whether the goal was achieved
            score: Optional quality score (0-1) for more granular feedback
            failure_reason: Optional reason for failure (helps with debugging)
            metadata: Optional additional context as a dict
            tool_id: Optional tool that was used (e.g., "serper", "browserless")
            execution_params: Optional execution parameters (e.g., {"temperature": 0.3})

        Returns:
            dict with:
                - status: "accepted" if successful
                - trace_id: The trace ID recorded
                - goal: The goal recorded

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            # Success case
            report_outcome(trace_id="abc123", goal="book_meeting", success=True)

            # Failure case with reason
            report_outcome(
                trace_id="abc123",
                goal="book_meeting",
                success=False,
                failure_reason="calendar_conflict"
            )
        """
        response = self._request(
            "POST",
            "/api/v1/intelligence/report-outcome",
            json={
                "trace_id": trace_id,
                "goal": goal,
                "success": success,
                "score": score,
                "failure_reason": failure_reason,
                "metadata": metadata,
                "tool_id": tool_id,
                "execution_params": execution_params,
            },
        )
        return response.json()

    def get_recommendation(
        self,
        task_type: str,
        goal: str | None = None,
        optimize_for: str = "balanced",
        constraints: dict | None = None,
        window_hours: int = 168,
    ) -> dict[str, Any]:
        """Get model recommendation for a task type.

        This is the original recommendation endpoint. For goal-based
        optimization, prefer get_policy() instead.

        Args:
            task_type: Type of task (e.g., "summarize", "code", "qa")
            goal: Optional goal for outcome-based optimization
            optimize_for: Optimization target - one of:
                - "cost": Minimize cost
                - "quality": Maximize output quality
                - "latency": Minimize response time
                - "balanced": Balance all factors (default)
                - "cost_efficiency": Maximize quality-per-dollar
                - "outcome": Optimize for goal success rate
            constraints: Optional constraints dict
            window_hours: Time window for pattern analysis

        Returns:
            dict with recommendation, alternatives, stats, reasoning
        """
        response = self._request(
            "POST",
            "/api/v1/intelligence/recommend",
            json={
                "task_type": task_type,
                "goal": goal,
                "optimize_for": optimize_for,
                "constraints": constraints,
                "window_hours": window_hours,
            },
        )
        return response.json()

    # =========================================================================
    # ROUTING METHODS
    # =========================================================================

    def register_path(
        self,
        goal: str,
        model_id: str,
        tool_id: str | None = None,
        params: dict | None = None,
        risk_level: str = "low",
    ) -> dict[str, Any]:
        """Register a new routing path for a goal.

        Creates a path that maps a goal to a specific model (and optionally tool)
        configuration. This path can then be selected by the decide() method.

        Args:
            goal: The goal this path is for (e.g., "book_meeting", "resolve_ticket")
            model_id: The model identifier to use (e.g., "gpt-4", "claude-3-opus")
            tool_id: Optional tool identifier if this path uses a specific tool
            params: Optional parameters dict for the path configuration
            risk_level: Risk level for this path - "low", "medium", or "high"

        Returns:
            dict with the created path including:
                - path_id: Unique identifier for the path
                - goal: The goal
                - model_id: The model
                - tool_id: The tool (if specified)
                - params: The parameters (if specified)
                - risk_level: The risk level
                - created_at: Creation timestamp

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            path = intelligence.register_path(
                goal="book_meeting",
                model_id="gpt-4",
                tool_id="calendar_tool",
                risk_level="low"
            )
            print(f"Created path: {path['path_id']}")
        """
        response = self._request(
            "POST",
            "/api/v1/routing/paths",
            json={
                "goal": goal,
                "model_id": model_id,
                "tool_id": tool_id,
                "params": params,
                "risk_level": risk_level,
            },
        )
        return response.json()

    def list_paths(
        self,
        goal: str | None = None,
        include_disabled: bool = False,
    ) -> dict[str, Any]:
        """List registered routing paths.

        Args:
            goal: Optional goal to filter paths by
            include_disabled: Whether to include disabled paths (default False)

        Returns:
            dict with:
                - paths: List of path objects

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            result = intelligence.list_paths(goal="book_meeting")
            for path in result["paths"]:
                print(f"{path['path_id']}: {path['model_id']}")
        """
        params = {}
        if goal is not None:
            params["goal"] = goal
        if include_disabled:
            params["include_disabled"] = "true"

        response = self._request(
            "GET",
            "/api/v1/routing/paths",
            params=params if params else None,
        )
        return response.json()

    def disable_path(self, path_id: str) -> dict[str, Any]:
        """Disable a routing path.

        Disables a path so it won't be selected by decide(). The path
        data is retained for historical analysis.

        Args:
            path_id: The unique identifier of the path to disable

        Returns:
            dict with:
                - status: "disabled" if successful
                - path_id: The disabled path ID

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            result = intelligence.disable_path("path_abc123")
            print(f"Status: {result['status']}")
        """
        response = self._request(
            "DELETE",
            f"/api/v1/routing/paths/{path_id}",
        )
        return response.json()

    def decide(
        self,
        goal: str,
        task_risk_level: str = "low",
    ) -> dict[str, Any]:
        """Get routing decision for a goal.

        Uses outcome data and exploration/exploitation strategy to decide
        which path to use for achieving the specified goal.

        Args:
            goal: The goal to route for (e.g., "book_meeting")
            task_risk_level: Risk tolerance for this task - "low", "medium", or "high"

        Returns:
            dict with:
                - model_id: The selected model
                - tool_id: The selected tool (if any)
                - params: Additional parameters (if any)
                - reason: Human-readable explanation of the decision
                - confidence: Confidence score (0-1)
                - is_exploration: Whether this is an exploration choice
                - path_id: The selected path ID

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            decision = intelligence.decide(goal="book_meeting")
            model = decision["model_id"]
            print(f"Using {model} ({decision['reason']})")
        """
        response = self._request(
            "POST",
            "/api/v1/routing/decide",
            json={
                "goal": goal,
                "task_risk_level": task_risk_level,
            },
        )
        return response.json()

    def set_exploration_config(
        self,
        goal: str = "*",
        exploration_rate: float = 0.1,
        min_samples_before_exploit: int = 20,
        rollback_threshold: float = 0.3,
        staleness_days: int = 7,
        exploration_on_high_risk: bool = False,
    ) -> dict[str, Any]:
        """Set exploration/exploitation configuration for routing.

        Configures how the decide() method balances exploring new paths
        vs exploiting known good paths.

        Args:
            goal: Goal to configure, or "*" for default config
            exploration_rate: Probability of exploring (0-1, default 0.1)
            min_samples_before_exploit: Minimum outcomes before exploiting (default 20)
            rollback_threshold: Performance drop threshold to rollback (default 0.3)
            staleness_days: Days before reexploring stale paths (default 7)
            exploration_on_high_risk: Whether to explore on high-risk tasks (default False)

        Returns:
            dict with the saved configuration

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            config = intelligence.set_exploration_config(
                goal="book_meeting",
                exploration_rate=0.2,
                min_samples_before_exploit=10
            )
        """
        response = self._request(
            "POST",
            "/api/v1/routing/config",
            json={
                "goal": goal,
                "exploration_rate": exploration_rate,
                "min_samples_before_exploit": min_samples_before_exploit,
                "rollback_threshold": rollback_threshold,
                "staleness_days": staleness_days,
                "exploration_on_high_risk": exploration_on_high_risk,
            },
        )
        return response.json()

    def get_exploration_config(self, goal: str | None = None) -> dict[str, Any]:
        """Get exploration/exploitation configuration.

        Args:
            goal: Optional goal to get config for (returns default if not found)

        Returns:
            dict with configuration values:
                - goal: The goal this config applies to
                - exploration_rate: Exploration probability
                - min_samples_before_exploit: Minimum samples before exploiting
                - rollback_threshold: Rollback threshold
                - staleness_days: Staleness threshold in days
                - exploration_on_high_risk: Whether exploration is allowed on high-risk

        Raises:
            httpx.HTTPStatusError: If the API returns an error

        Example:
            config = intelligence.get_exploration_config(goal="book_meeting")
            print(f"Exploration rate: {config['exploration_rate']}")
        """
        params = {}
        if goal is not None:
            params["goal"] = goal

        response = self._request(
            "GET",
            "/api/v1/routing/config",
            params=params if params else None,
        )
        return response.json()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Module-level singleton for convenience functions
_intelligence_client: KalibrIntelligence | None = None


def _get_intelligence_client() -> KalibrIntelligence:
    """Get or create the singleton intelligence client."""
    global _intelligence_client
    if _intelligence_client is None:
        _intelligence_client = KalibrIntelligence()
    return _intelligence_client


def get_policy(goal: str, tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
    """Get execution policy for a goal.

    Convenience function that uses the default intelligence client.
    See KalibrIntelligence.get_policy for full documentation.

    Args:
        goal: The goal to optimize for
        tenant_id: Optional tenant ID override (default: uses KALIBR_TENANT_ID env var)
        **kwargs: Additional arguments (task_type, constraints, window_hours)

    Returns:
        Policy dict with recommended_model, outcome_success_rate, etc.

    Example:
        from kalibr import get_policy

        policy = get_policy(goal="book_meeting")
        model = policy["recommended_model"]
    """
    client = _get_intelligence_client()
    if tenant_id:
        # Create a new client with the specified tenant_id
        client = KalibrIntelligence(tenant_id=tenant_id)
    return client.get_policy(goal, **kwargs)


def report_outcome(trace_id: str, goal: str, success: bool, tenant_id: str | None = None, **kwargs) -> dict[str, Any]:
    """Report execution outcome for a goal.

    Convenience function that uses the default intelligence client.
    See KalibrIntelligence.report_outcome for full documentation.

    Args:
        trace_id: The trace ID from the execution
        goal: The goal this execution was trying to achieve
        success: Whether the goal was achieved
        tenant_id: Optional tenant ID override (default: uses KALIBR_TENANT_ID env var)
        **kwargs: Additional arguments (score, failure_reason, metadata, tool_id, execution_params)

    Returns:
        Response dict with status confirmation

    Example:
        from kalibr import report_outcome

        report_outcome(trace_id="abc123", goal="book_meeting", success=True)
    """
    client = _get_intelligence_client()
    if tenant_id:
        # Create a new client with the specified tenant_id
        client = KalibrIntelligence(tenant_id=tenant_id)
    return client.report_outcome(trace_id, goal, success, **kwargs)


def get_recommendation(task_type: str, **kwargs) -> dict[str, Any]:
    """Get model recommendation for a task type.

    Convenience function that uses the default intelligence client.
    See KalibrIntelligence.get_recommendation for full documentation.
    """
    return _get_intelligence_client().get_recommendation(task_type, **kwargs)


def register_path(
    goal: str,
    model_id: str,
    tool_id: str | None = None,
    params: dict | None = None,
    risk_level: str = "low",
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Register a new routing path for a goal.

    Convenience function that uses the default intelligence client.
    See KalibrIntelligence.register_path for full documentation.

    Args:
        goal: The goal this path is for
        model_id: The model identifier to use
        tool_id: Optional tool identifier
        params: Optional parameters dict
        risk_level: Risk level - "low", "medium", or "high"
        tenant_id: Optional tenant ID override

    Returns:
        dict with the created path

    Example:
        from kalibr import register_path

        path = register_path(
            goal="book_meeting",
            model_id="gpt-4",
            tool_id="calendar_tool"
        )
    """
    client = _get_intelligence_client()
    if tenant_id:
        client = KalibrIntelligence(tenant_id=tenant_id)
    return client.register_path(goal, model_id, tool_id, params, risk_level)


def decide(
    goal: str,
    task_risk_level: str = "low",
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Get routing decision for a goal.

    Convenience function that uses the default intelligence client.
    See KalibrIntelligence.decide for full documentation.

    Args:
        goal: The goal to route for
        task_risk_level: Risk tolerance - "low", "medium", or "high"
        tenant_id: Optional tenant ID override

    Returns:
        dict with model_id, tool_id, params, reason, confidence, etc.

    Example:
        from kalibr import decide

        decision = decide(goal="book_meeting")
        model = decision["model_id"]
    """
    client = _get_intelligence_client()
    if tenant_id:
        client = KalibrIntelligence(tenant_id=tenant_id)
    return client.decide(goal, task_risk_level)
