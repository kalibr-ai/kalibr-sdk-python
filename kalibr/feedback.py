"""
kalibr_feedback.py — User behavioral signal → Kalibr learning loop

Usage in OpenClaw/agents:

    from kalibr.feedback import KalibrFeedback

    # After a pipeline run:
    feedback = KalibrFeedback()
    feedback.set_last_run(trace_id=result["trace_id"], goal=result["goal"])

    # When user rejects:
    feedback.reject(reason="output was too short")

    # When user accepts (implicit or explicit):
    feedback.accept(score=0.9)

This feeds directly into Kalibr's global priors via update_outcome().
User prompts are never sent — only the trace_id, goal, and outcome.
"""

import os
from typing import Optional


class KalibrFeedback:
    """
    Lightweight wrapper that stores the last Kalibr trace context
    and allows signaling user accept/reject back to the intelligence service.
    """

    def __init__(self):
        self._trace_id: Optional[str] = None
        self._goal: Optional[str] = None
        self._api_key = os.environ.get("KALIBR_API_KEY")
        self._tenant_id = os.environ.get("KALIBR_TENANT_ID")
        self._base_url = os.environ.get(
            "KALIBR_INTELLIGENCE_URL", "https://kalibr-intelligence.fly.dev"
        )

    def set_last_run(self, trace_id: str, goal: str) -> None:
        """
        Call this after every router.completion() or pipeline run.
        Stores the trace context so reject()/accept() can reference it.
        """
        self._trace_id = trace_id
        self._goal = goal

    def reject(self, reason: str = "") -> bool:
        """
        Signal that the user rejected the output from the last run.
        Maps to failure_category='user_unsatisfied' in Kalibr.

        Returns True if the signal was sent successfully.
        """
        return self._send_outcome(
            success=False,
            failure_category="user_unsatisfied",
            failure_reason=reason or "user rejected output",
        )

    def accept(self, score: float = 0.85) -> bool:
        """
        Signal that the user accepted the output from the last run.
        A score of 0.85 means "good, used without complaint."
        A score of 1.0 means "explicitly great."

        Returns True if the signal was sent successfully.
        """
        return self._send_outcome(success=True, score=score)

    def _send_outcome(
        self,
        success: bool,
        score: Optional[float] = None,
        failure_category: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> bool:
        if not self._trace_id or not self._goal:
            return False
        if not self._api_key or not self._tenant_id:
            return False

        try:
            from kalibr.intelligence import update_outcome
            result = update_outcome(
                trace_id=self._trace_id,
                goal=self._goal,
                success=success,
                score=score,
                failure_reason=failure_reason,
                failure_category=failure_category,
            )
            return True
        except ImportError:
            # Fall back to direct HTTP if kalibr SDK not available
            return self._send_outcome_http(success, score, failure_category, failure_reason)
        except Exception as e:
            print(f"[KalibrFeedback] update_outcome failed: {e}")
            return False

    def _send_outcome_http(self, success, score, failure_category, failure_reason) -> bool:
        """Direct HTTP fallback when kalibr SDK unavailable."""
        try:
            import requests
            payload = {
                "trace_id": self._trace_id,
                "goal": self._goal,
                "success": success,
            }
            if score is not None:
                payload["score"] = score
            if failure_category:
                payload["failure_category"] = failure_category
            if failure_reason:
                payload["failure_reason"] = failure_reason

            r = requests.post(
                f"{self._base_url}/api/v1/intelligence/update-outcome",
                headers={
                    "X-API-Key": self._api_key,
                    "X-Tenant-ID": self._tenant_id,
                },
                json=payload,
                timeout=3,
            )
            return r.status_code in (200, 201)
        except Exception as e:
            print(f"[KalibrFeedback] HTTP fallback failed: {e}")
            return False

    @property
    def has_context(self) -> bool:
        """True if there's a pending trace to report on."""
        return bool(self._trace_id and self._goal)

    def __repr__(self):
        return f"KalibrFeedback(trace_id={self._trace_id!r}, goal={self._goal!r})"


# ── Convenience functions for OpenClaw AGENTS.md integration ──────────────────

_global_feedback = KalibrFeedback()


def track_run(result: dict) -> None:
    """
    Call after every classify_and_route() or pipeline run.

    result should be the dict returned by run_step() or classify_and_route(),
    which includes trace_id and goal keys.

    Usage in AGENTS.md agent loop:
        result = classify_and_route(user_request)
        track_run(result)
    """
    trace_id = result.get("trace_id") or result.get("kalibr_trace_id")
    goal = result.get("goal") or result.get("goal_id")
    if trace_id and goal:
        _global_feedback.set_last_run(trace_id=trace_id, goal=goal)


def user_rejected(reason: str = "") -> bool:
    """
    Call when the user says 'redo this', 'that's wrong', 'try again'.
    Signals failure to Kalibr. Updates global priors.

    Usage:
        if agent_detects_rejection():
            user_rejected("output was too short")
    """
    return _global_feedback.reject(reason=reason)


def user_accepted(score: float = 0.85) -> bool:
    """
    Call when the user uses the output without complaint, or explicitly approves.
    Signals success to Kalibr. Updates global priors.

    Usage:
        if agent_detects_acceptance():
            user_accepted()
    """
    return _global_feedback.accept(score=score)


def get_feedback() -> KalibrFeedback:
    """Get the global feedback instance (if you need direct access)."""
    return _global_feedback
