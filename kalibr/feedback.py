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
import threading
import time
import uuid
import logging
from typing import Optional

logger = logging.getLogger("kalibr.feedback")

_session_locks: dict = {}
_session_locks_mutex = threading.Lock()


def _get_session_lock(session_id: str):
    with _session_locks_mutex:
        if session_id not in _session_locks:
            _session_locks[session_id] = threading.Lock()
        return _session_locks[session_id]


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


# ── Generic signal emission ───────────────────────────────────────────────────

def _emit_signal_http(
    base_url: str,
    api_key: str,
    tenant_id: str,
    payload: dict,
) -> bool:
    """Internal helper to POST a signal payload. Returns True on success."""
    try:
        import requests
        r = requests.post(
            f"{base_url}/api/v1/intelligence/signals",
            headers={"X-API-Key": api_key, "X-Tenant-ID": tenant_id},
            json=payload,
            timeout=3,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def _get_session_path(session_id: str) -> pathlib.Path:
    return pathlib.Path(os.path.expanduser(f"~/.kalibr/sessions/{session_id}.json"))


def _read_session(session_id: str) -> Optional[dict]:
    """Read session file; returns None if missing or expired (>30 min)."""
    try:
        path = _get_session_path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        if time.time() - data.get("ts", 0) > 1800:
            return None
        return data
    except Exception:
        return None


def _fb_config() -> tuple:
    """Return (api_key, tenant_id, base_url) from global feedback singleton."""
    fb = get_feedback()
    return fb._api_key, fb._tenant_id, fb._base_url


# ── Behavioral Signal SDK (v1.12.0) ────────────────────────────────────────


def report_pipeline(
    session_id: str,
    goal: str,
    prompt: str,
    output: str,
    model: str,
    meta_prompt_id: Optional[str] = None,
) -> None:
    """
    Anchor a pipeline run so downstream signals can correlate back.

    Writes a pipeline_anchor signal AND persists session context to
    ~/.kalibr/sessions/{session_id}.json (TTL 30 min).
    """
    try:
        api_key, tenant_id, base_url = _fb_config()
        trace_id = str(uuid.uuid4())

        # Persist session file
        session_dir = pathlib.Path(os.path.expanduser("~/.kalibr/sessions"))
        session_dir.mkdir(parents=True, exist_ok=True)
        session_data = {
            "trace_id": trace_id,
            "goal": goal,
            "prompt": prompt,
            "output_snippet": output[:200],
            "model": model,
            "meta_prompt_id": meta_prompt_id,
            "ts": time.time(),
            "deltas": [],
            "momentum": "flat",
            "last_user_message": "",
        }
        _get_session_path(session_id).write_text(json.dumps(session_data))

        # Fire signal
        if api_key and tenant_id:
            payload = {
                "trace_id": trace_id,
                "signal_type": "pipeline_anchor",
                "signal_source": "pipeline",
                "strength": 0.5,
                "confidence": 1.0,
                "goal": goal,
                "model": model,
                "session_id": session_id,
            }
            if meta_prompt_id:
                payload["meta_prompt_id"] = meta_prompt_id
            _emit_signal_http(base_url, api_key, tenant_id, payload)
    except Exception as e:
        logger.warning("report_pipeline failed: %s", e)


def _jaccard_similarity(text1: str, text2: str) -> float:
    """Jaccard similarity between two texts. No model needed."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return 0.5
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.5


_FRUST_WORDS = {"again", "wrong", "bad", "no", "fix", "redo", "useless", "terrible", "horrible", "stop", "different", "change", "not what"}
_AFFIRM_WORDS = {"thanks", "perfect", "great", "yes", "good", "exactly", "awesome", "love", "correct", "nice"}


def _compute_delta(prev_msg: str, curr_msg: str) -> dict:
    """Compute delta between two consecutive user messages."""
    return {
        "jaccard": _jaccard_similarity(prev_msg, curr_msg),
        "len_ratio": len(curr_msg) / max(len(prev_msg), 1),
        "frust": sum(1 for w in _FRUST_WORDS if w in curr_msg.lower()),
        "affirm": sum(1 for w in _AFFIRM_WORDS if w in curr_msg.lower()),
    }


def _compute_momentum(deltas: list) -> str:
    """
    Compute conversation momentum from last 4 deltas.
    closing = user converging (satisfied, getting what they want)
    widening = user diverging (frustrated, not getting what they want)
    flat = no clear trend
    """
    if not deltas or len(deltas) < 2:
        return "flat"
    recent = deltas[-4:]
    avg_jaccard = sum(d["jaccard"] for d in recent) / len(recent)
    avg_len = sum(d["len_ratio"] for d in recent) / len(recent)
    total_frust = sum(d["frust"] for d in recent)
    total_affirm = sum(d["affirm"] for d in recent)

    if avg_jaccard > 0.50 and avg_len < 1.1 and total_frust == 0:
        return "closing"
    if total_affirm >= 2 and total_frust == 0 and avg_len < 1.2:
        return "closing"
    if avg_jaccard < 0.35 or total_frust > 1 or (avg_len > 1.3 and total_frust >= 1):
        return "widening"
    return "flat"


def report_user_turn(session_id: str, user_message: str) -> None:
    """
    Classify a user follow-up message against the anchored session.

    Layer 1: heuristic keyword check (fast).
    Layer 2: LLM classifier in background thread if confidence < 0.85.
    Never blocks the caller.
    """
    try:
        lock = _get_session_lock(session_id)
        with lock:
            session = _read_session(session_id)
            if session is None:
                return

            # Delta tracking
            prev_msg = session.get("last_user_message", "")
            if prev_msg:
                delta = _compute_delta(prev_msg, user_message)
                deltas = session.get("deltas", [])
                deltas.append(delta)
                if len(deltas) > 8:
                    deltas = deltas[-8:]
                session["deltas"] = deltas
                session["momentum"] = _compute_momentum(deltas)
            session["last_user_message"] = user_message
            # Persist session with updated delta state
            _get_session_path(session_id).write_text(json.dumps(session))

            api_key, tenant_id, base_url = _fb_config()
            if not api_key or not tenant_id:
                return

            # Layer 1 — heuristic classifier
            confidence, signal_type, dimensions = _heuristic_classify(user_message)

            if confidence >= 0.85:
                _fire_user_turn_signal(
                    base_url, api_key, tenant_id, session, session_id,
                    signal_type, confidence, dimensions, user_message,
                    momentum=session.get("momentum", "flat"),
                )
            else:
                # Fire LLM classifier in background thread
                t = threading.Thread(
                    target=_llm_classify_and_send,
                    args=(base_url, api_key, tenant_id, session, session_id, user_message),
                    daemon=True,
                )
                t.start()
    except Exception as e:
        logger.warning("report_user_turn failed: %s", e)


_REJECTION_KEYWORDS = {
    "redo", "try again", "wrong", "no", "that's not", "too long", "too short",
    "rewrite", "start over", "not what i", "change", "fix",
}
_ACCEPTANCE_KEYWORDS = {
    "thanks", "perfect", "great", "looks good", "awesome", "love it", "exactly",
    "good job", "well done", "nice",
}


def _heuristic_classify(user_message: str) -> tuple:
    """Returns (confidence, signal_type, dimensions)."""
    msg_lower = user_message.lower()

    # Try importing the existing reprompt_classifier if available
    try:
        from kalibr.reprompt_classifier import classify as _rc_classify
        result = _rc_classify(msg_lower)
        return result.get("confidence", 0.5), result.get("type", "neutral"), result.get("dimensions", [])
    except (ImportError, Exception):
        pass

    # Simple keyword fallback
    rejection_hits = sum(1 for kw in _REJECTION_KEYWORDS if kw in msg_lower)
    acceptance_hits = sum(1 for kw in _ACCEPTANCE_KEYWORDS if kw in msg_lower)

    if rejection_hits > acceptance_hits and rejection_hits >= 1:
        conf = min(0.6 + rejection_hits * 0.15, 0.95)
        return conf, "user_rejected", []
    elif acceptance_hits > rejection_hits and acceptance_hits >= 1:
        conf = min(0.6 + acceptance_hits * 0.15, 0.95)
        return conf, "user_accepted", []

    return 0.3, "unrelated", []


def _fire_user_turn_signal(
    base_url, api_key, tenant_id, session, session_id,
    signal_type, confidence, dimensions, raw_evidence,
    momentum: str = "flat",
):
    # Drop unrelated/neutral signals — absence of reaction is not a signal
    if signal_type not in ("user_rejected", "user_accepted"):
        return
    strength = 0.0 if signal_type == "user_rejected" else 1.0
    payload = {
        "trace_id": session.get("trace_id", ""),
        "signal_type": signal_type,
        "signal_source": "user_implicit",
        "strength": strength,
        "confidence": confidence,
        "goal": session.get("goal", ""),
        "session_id": session_id,
        "raw_evidence": raw_evidence[:500],
        # TODO: re-enable once API schema accepts momentum field
        # "momentum": momentum,
    }
    if dimensions:
        payload["dimensions"] = dimensions
    _emit_signal_http(base_url, api_key, tenant_id, payload)


_LLM_CLASSIFY_PROMPT = (
    "Prior goal: {goal}. User message: {user_message}. "
    "Did user: (A) accept and move on, (B) reject and re-prompt, (C) unrelated. "
    "If B, which dimensions failed: length/tone/format/content/factuality. "
    'Return JSON: {{"type": "acceptance"|"rejection"|"neutral", "confidence": 0.0-1.0, "dimensions": [...]}}'
)


def _llm_classify_and_send(base_url, api_key, tenant_id, session, session_id, user_message):
    """Run LLM classifier and send the resulting signal. Runs in background thread."""
    try:
        prompt = _LLM_CLASSIFY_PROMPT.format(
            goal=session.get("goal", ""),
            user_message=user_message[:400],
        )

        raw = None
        # Try DeepSeek first, then OpenAI
        for env_key, model_id, api_base in [
            ("DEEPSEEK_API_KEY", "deepseek-chat", "https://api.deepseek.com"),
            ("OPENAI_API_KEY", "gpt-4o-mini", None),
        ]:
            key = os.environ.get(env_key)
            if not key:
                continue
            try:
                import openai as _openai
                kwargs = {"api_key": key}
                if api_base:
                    kwargs["base_url"] = api_base
                client = _openai.OpenAI(**kwargs)
                resp = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=120,
                    temperature=0.0,
                )
                raw = (resp.choices[0].message.content or "").strip()
                break
            except Exception:
                continue

        if not raw:
            return

        # Parse JSON from LLM response
        result = json.loads(raw)
        signal_type = result.get("type", "neutral")
        confidence = float(result.get("confidence", 0.5))
        dimensions = result.get("dimensions", [])

        try:
            s = _read_session(session_id)
            cur_momentum = s.get("momentum", "flat") if s else "flat"
        except Exception:
            cur_momentum = "flat"

        _fire_user_turn_signal(
            base_url, api_key, tenant_id, session, session_id,
            signal_type, confidence, dimensions, user_message,
            momentum=cur_momentum,
        )
    except Exception as e:
        logger.warning("LLM classify failed: %s", e)


_ACTION_STRENGTH = {
    "output_used_verbatim": 1.0,
    "output_copied": 0.9,
    "output_edited": 0.4,
    "output_discarded": 0.0,
}


def report_action(
    session_id: str,
    action_type: str,
    edit_diff: Optional[str] = None,
) -> None:
    """
    Record a downstream action on the pipeline output.

    action_type: "output_used_verbatim" | "output_edited" | "output_copied" | "output_discarded"
    Highest-quality signal — overrides any pending classifier result.
    Fire-and-forget.
    """
    try:
        session = _read_session(session_id)
        if session is None:
            return

        api_key, tenant_id, base_url = _fb_config()
        if not api_key or not tenant_id:
            return

        strength = _ACTION_STRENGTH.get(action_type, 0.5)
        payload = {
            "trace_id": session.get("trace_id", ""),
            "signal_type": action_type,
            "signal_source": "downstream",
            "strength": strength,
            "confidence": 1.0,
            "goal": session.get("goal", ""),
            "session_id": session_id,
        }
        if edit_diff:
            payload["raw_evidence"] = edit_diff[:500]

        def _send():
            try:
                _emit_signal_http(base_url, api_key, tenant_id, payload)
            except Exception:
                pass

        threading.Thread(target=_send, daemon=True).start()
    except Exception as e:
        logger.warning("report_action failed: %s", e)


def emit_signal(
    signal_type: str,
    strength: float = 0.5,
    dimension: str = "",
    raw_evidence: str = "",
    pipeline_step: int = 0,
    confidence: float = 1.0,
    trace_id: str | None = None,
    goal: str | None = None,
) -> bool:
    """
    Emit a behavioral signal to the Kalibr signals endpoint.

    This is the low-level signal emission function. For most use cases,
    use user_rejected(), user_accepted(), or classify_satisfaction() instead.

    signal_type options:
      'user_rejected'    — explicit user rejection
      'user_accepted'    — explicit user acceptance  
      'downstream_use'   — output was used verbatim in next step
      'edit_small'       — output was used but lightly edited
      'edit_large'       — output was substantially rewritten
      'abandonment'      — session ended without using output
      'retry'            — user requested a redo

    strength: 0.0 = strong negative, 1.0 = strong positive, 0.5 = neutral

    dimension: 'tone' | 'format' | 'length' | 'factuality' | 'completeness' | 'overall'
    """
    fb = get_feedback()
    # Load from disk if not in memory
    if not fb._trace_id:
        fb._load_from_disk()

    effective_trace_id = trace_id or fb._trace_id
    effective_goal = goal or fb._goal

    if not effective_trace_id:
        return False

    api_key = fb._api_key
    tenant_id = fb._tenant_id
    base_url = fb._base_url

    if not api_key or not tenant_id:
        return False

    try:
        import requests
        payload = {
            "trace_id": effective_trace_id,
            "signal_type": signal_type,
            "signal_source": "user_explicit" if signal_type in ("user_rejected", "user_accepted") else "user_implicit",
            "strength": strength,
            "confidence": confidence,
            "dimension": dimension,
            "goal": effective_goal or "",
            "raw_evidence": raw_evidence[:500] if raw_evidence else "",
            "pipeline_step": pipeline_step,
        }
        r = requests.post(
            f"{base_url}/api/v1/signals",
            headers={"X-API-Key": api_key, "X-Tenant-ID": tenant_id},
            json=payload,
            timeout=3,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def report_session_end(session_id: str) -> None:
    """
    Fire a weak behavioral signal when a session ends without explicit feedback.

    Uses conversation momentum (delta trajectory) to determine signal direction:
    - closing momentum → weak positive (user probably got value and left)
    - widening momentum → weak negative (user probably gave up)
    - flat momentum → no signal emitted (silence without context = noise)

    Always fires with low confidence (0.4) so it cannot dominate real signals.
    Requires at least 2 deltas in session history — otherwise emits nothing.

    Call this when:
    - Session timeout detected
    - User explicitly closes/ends the conversation
    - Application session lifecycle ends
    """
    try:
        session = _read_session(session_id)
        if session is None:
            return

        deltas = session.get("deltas", [])
        if len(deltas) < 2:
            return  # not enough trajectory data — silence is just noise

        mom = _compute_momentum(deltas)
        if mom == "flat":
            return  # no interpretable signal

        # closing = user got value and left → weak positive
        # widening = user gave up → weak negative
        strength = 0.65 if mom == "closing" else 0.25
        signal_type = "user_accepted" if mom == "closing" else "user_rejected"

        emit_signal(
            signal_type=signal_type,
            strength=strength,
            confidence=0.4,  # always low — inferred from silence, inherently uncertain
            trace_id=session.get("trace_id", ""),
            goal=session.get("goal", ""),
            raw_evidence="session_end_inferred",
        )

        logger.debug(
            "session_end_signal",
            session_id=session_id,
            momentum=mom,
            signal_type=signal_type,
            strength=strength,
            delta_count=len(deltas),
        )
    except Exception as e:
        logger.warning("report_session_end failed: %s", e)
