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
import json
import pathlib
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
        Also persists to disk so feedback works across sessions.
        """
        self._trace_id = trace_id
        self._goal = goal
        # Persist to disk for cross-session feedback
        try:
            cache_path = pathlib.Path(os.path.expanduser("~/.kalibr/last_trace.json"))
            cache_path.parent.mkdir(exist_ok=True)
            cache_path.write_text(json.dumps({"trace_id": trace_id, "goal": goal}))
        except Exception:
            pass  # non-critical

    def _load_from_disk(self) -> bool:
        """Load last trace context from disk if not in memory."""
        if self._trace_id:
            return True
        try:
            cache_path = pathlib.Path(os.path.expanduser("~/.kalibr/last_trace.json"))
            if cache_path.exists():
                data = json.loads(cache_path.read_text())
                self._trace_id = data.get("trace_id")
                self._goal = data.get("goal")
                return bool(self._trace_id)
        except Exception:
            pass
        return False

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
        # Try loading from disk if not in memory (cross-session support)
        if not self._trace_id or not self._goal:
            self._load_from_disk()
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


# ── Semantic satisfaction classifier ─────────────────────────────────────────

_SATISFACTION_PROMPT = """You are classifying user satisfaction with an AI output.

Prior AI output:
{prior_output}

User's follow-up message:
{user_message}

Based only on the user's follow-up, classify their satisfaction:
- "negative": user is dissatisfied, wants a change, retry, or is expressing criticism
- "positive": user is satisfied, approves, or is moving forward with the output
- "neutral": user is asking a clarifying question, continuing the conversation, or no clear signal

Respond with ONLY one of: negative, positive, neutral"""


def classify_satisfaction(
    user_message: str,
    prior_output: str,
    model: str = "deepseek-chat",
) -> str:
    """
    Classify user satisfaction with the prior Kalibr output.

    Uses a cheap LLM to semantically interpret the user's follow-up message.
    Never uses keyword matching. Returns "negative", "positive", or "neutral".

    This is the right way to detect rejection — not keyword lists.
    The orchestrator already has this context; this makes it explicit and persistent.

    Args:
        user_message: The user's follow-up message after seeing Kalibr's output
        prior_output: The output that Kalibr produced in the prior step
        model: Model to use for classification (default: deepseek-chat — cheap and fast)

    Returns:
        "negative" | "positive" | "neutral"

    Usage in agent loop:
        result = classify_satisfaction(
            user_message=user_turn,
            prior_output=last_output,
        )
        if result == "negative":
            user_rejected()
        elif result == "positive":
            user_accepted()

    Fire-and-forget async version available via classify_satisfaction_async().
    """
    if not user_message or not prior_output:
        return "neutral"

    prompt = _SATISFACTION_PROMPT.format(
        prior_output=prior_output[:800],
        user_message=user_message[:400],
    )

    # Try providers in order of preference (cheap models only)
    providers = [
        ("deepseek", "deepseek-chat", "https://api.deepseek.com"),
        ("openai", "gpt-4o-mini", None),
        ("anthropic", "claude-haiku-3-5-20241022", None),
    ]

    for provider_name, model_id, base_url in providers:
        api_key = os.environ.get(f"{provider_name.upper()}_API_KEY")
        if not api_key:
            continue
        try:
            import openai as _openai
            if provider_name == "anthropic":
                import anthropic as _anthropic
                client = _anthropic.Anthropic(api_key=api_key)
                resp = client.messages.create(
                    model=model_id,
                    max_tokens=10,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.content[0].text.strip().lower()
            else:
                kwargs = {"api_key": api_key}
                if base_url:
                    kwargs["base_url"] = base_url
                client = _openai.OpenAI(**kwargs)
                resp = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=10,
                    temperature=0.0,
                )
                raw = (resp.choices[0].message.content or "").strip().lower()

            if "negative" in raw:
                return "negative"
            elif "positive" in raw:
                return "positive"
            else:
                return "neutral"

        except Exception:
            continue

    # No provider available — return neutral (fail open, never block)
    return "neutral"


async def classify_satisfaction_async(
    user_message: str,
    prior_output: str,
) -> str:
    """
    Async version of classify_satisfaction. Fire-and-forget friendly.
    Same semantics, same return values.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        classify_satisfaction,
        user_message,
        prior_output,
    )
