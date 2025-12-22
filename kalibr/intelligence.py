"""Kalibr Intelligence Client - Query execution intelligence and report outcomes.

This module enables the outcome-conditioned routing loop:
1. Before executing: query get_policy() to get the best path for your goal
2. After executing: call report_outcome() to teach Kalibr what worked

Example:
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
"""

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
    ) -> httpx.Response:
        """Make authenticated request to intelligence API."""
        headers = {
            "X-API-Key": self.api_key,
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{path}"
        response = self._client.request(method, url, json=json, headers=headers)
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
        **kwargs: Additional arguments (score, failure_reason, metadata)

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
