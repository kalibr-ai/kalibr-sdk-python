"""
Kalibr Router - Intelligent model routing with outcome learning.
"""

import os
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

from opentelemetry import trace as otel_trace

logger = logging.getLogger(__name__)

# Type for paths - either string or dict
PathSpec = Union[str, Dict[str, Any]]


class Router:
    """
    Routes LLM requests to the best model based on learned outcomes.

    Example:
        router = Router(
            goal="summarize",
            paths=["gpt-4o", "claude-3-sonnet"],
            success_when=lambda out: len(out) > 100
        )
        response = router.completion(messages=[...])
    """

    def __init__(
        self,
        goal: str,
        paths: Optional[List[PathSpec]] = None,
        success_when: Optional[Callable[[str], bool]] = None,
        exploration_rate: Optional[float] = None,
        auto_register: bool = True,
    ):
        """
        Initialize router.

        Args:
            goal: Name of the goal (e.g., "book_meeting", "summarize")
            paths: List of models or path configs. Examples:
                   ["gpt-4o", "claude-3-sonnet"]
                   [{"model": "gpt-4o", "tools": ["search"]}]
            success_when: Optional function to auto-evaluate success from output
            exploration_rate: Override exploration rate (0.0-1.0)
            auto_register: If True, register paths on init
        """
        self.goal = goal
        self.success_when = success_when
        self.exploration_rate = exploration_rate
        self._last_trace_id: Optional[str] = None
        self._last_model_id: Optional[str] = None
        self._last_decision: Optional[dict] = None
        self._outcome_reported = False

        # Normalize paths to list of dicts
        self._paths = self._normalize_paths(paths or ["gpt-4o"])

        # Register paths if requested
        if auto_register:
            self._register_paths()

    def _normalize_paths(self, paths: List[PathSpec]) -> List[Dict[str, Any]]:
        """Convert paths to consistent format."""
        normalized = []
        for p in paths:
            if isinstance(p, str):
                normalized.append({"model": p, "tools": None, "params": None})
            elif isinstance(p, dict):
                normalized.append({
                    "model": p.get("model") or p.get("model_id"),
                    "tools": p.get("tools") or p.get("tool_id"),
                    "params": p.get("params"),
                })
            else:
                raise ValueError(f"Invalid path spec: {p}")
        return normalized

    def _register_paths(self):
        """Register paths with intelligence service."""
        from kalibr.intelligence import register_path

        for path in self._paths:
            try:
                register_path(
                    goal=self.goal,
                    model_id=path["model"],
                    tool_id=path["tools"][0] if isinstance(path["tools"], list) and path["tools"] else path["tools"],
                    params=path["params"],
                )
            except Exception as e:
                # Log but don't fail - path might already exist
                logger.debug(f"Path registration note: {e}")

    def completion(
        self,
        messages: List[Dict[str, str]],
        force_model: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Make a completion request with intelligent routing.

        Args:
            messages: OpenAI-format messages
            force_model: Override routing and use this model
            **kwargs: Additional args passed to provider

        Returns:
            OpenAI-compatible ChatCompletion response
        """
        from kalibr.intelligence import decide

        tracer = otel_trace.get_tracer("kalibr.router")

        with tracer.start_as_current_span(
            "kalibr.router.completion",
            attributes={
                "kalibr.goal": self.goal,
            }
        ) as router_span:
            # Reset state for new request
            self._outcome_reported = False

            # Get routing decision (or use forced model)
            if force_model:
                model_id = force_model
                tool_id = None
                params = {}
                self._last_decision = {"model_id": model_id, "forced": True}
                router_span.set_attribute("kalibr.model_id", model_id)
                router_span.set_attribute("kalibr.forced", True)
            else:
                try:
                    decision = decide(goal=self.goal)
                    model_id = decision.get("model_id") or self._paths[0]["model"]
                    tool_id = decision.get("tool_id")
                    params = decision.get("params") or {}
                    self._last_decision = decision

                    # Add decision attributes to span
                    router_span.set_attribute("kalibr.path_id", decision.get("path_id", ""))
                    router_span.set_attribute("kalibr.model_id", model_id)
                    router_span.set_attribute("kalibr.reason", decision.get("reason", ""))
                    router_span.set_attribute("kalibr.exploration", decision.get("exploration", False))
                    router_span.set_attribute("kalibr.confidence", decision.get("confidence", 0.0))
                except Exception as e:
                    # Fallback to first path if routing fails
                    logger.warning(f"Routing failed, using fallback: {e}")
                    model_id = self._paths[0]["model"]
                    tool_id = self._paths[0].get("tools")
                    params = self._paths[0].get("params") or {}
                    self._last_decision = {"model_id": model_id, "fallback": True, "error": str(e)}
                    router_span.set_attribute("kalibr.model_id", model_id)
                    router_span.set_attribute("kalibr.fallback", True)
                    router_span.set_attribute("kalibr.fallback_reason", str(e))

            # Store trace_id from THIS span for outcome reporting
            span_context = router_span.get_span_context()
            trace_id = format(span_context.trace_id, "032x")
            # Check if trace_id is valid (not all zeros from unconfigured tracer)
            if trace_id == "0" * 32:
                trace_id = uuid.uuid4().hex
            self._last_trace_id = trace_id
            self._last_model_id = model_id

            # Dispatch to provider (will be child span via auto-instrumentation)
            try:
                response = self._dispatch(model_id, messages, tool_id, **{**params, **kwargs})

                # Auto-report if success_when provided
                if self.success_when and not self._outcome_reported:
                    try:
                        output = response.choices[0].message.content or ""
                        success = self.success_when(output)
                        self.report(success=success)
                    except Exception as e:
                        logger.warning(f"Auto-outcome evaluation failed: {e}")

                return response

            except Exception as e:
                # Record error on span
                router_span.set_attribute("error", True)
                router_span.set_attribute("error.type", type(e).__name__)

                # Auto-report failure
                if not self._outcome_reported:
                    try:
                        self.report(success=False, reason=f"provider_error: {type(e).__name__}")
                    except:
                        pass
                raise

    def report(
        self,
        success: bool,
        reason: Optional[str] = None,
        score: Optional[float] = None,
    ):
        """
        Report outcome for the last completion.

        Args:
            success: Whether the task succeeded
            reason: Optional failure reason
            score: Optional quality score (0.0-1.0)
        """
        if self._outcome_reported:
            logger.warning("Outcome already reported for this request")
            return

        from kalibr.intelligence import report_outcome

        trace_id = self._last_trace_id
        if not trace_id:
            # Generate fallback trace_id if none available
            trace_id = uuid.uuid4().hex

        try:
            report_outcome(
                trace_id=trace_id,
                goal=self.goal,
                success=success,
                score=score,
                failure_reason=reason,
                model_id=self._last_model_id,
            )
            self._outcome_reported = True
        except Exception as e:
            logger.warning(f"Failed to report outcome: {e}")

    def add_path(
        self,
        model: str,
        tools: Optional[List[str]] = None,
        params: Optional[Dict] = None,
    ):
        """Add a new path dynamically."""
        from kalibr.intelligence import register_path

        path = {"model": model, "tools": tools, "params": params}
        self._paths.append(path)

        register_path(
            goal=self.goal,
            model_id=model,
            tool_id=tools[0] if tools else None,
            params=params,
        )

    def _dispatch(
        self,
        model_id: str,
        messages: List[Dict],
        tools: Optional[Any] = None,
        **kwargs
    ) -> Any:
        """Dispatch to the appropriate provider."""
        if model_id.startswith(("gpt-", "o1-", "o3-")):
            return self._call_openai(model_id, messages, tools, **kwargs)
        elif model_id.startswith("claude-"):
            return self._call_anthropic(model_id, messages, tools, **kwargs)
        elif model_id.startswith(("gemini-", "models/gemini")):
            return self._call_google(model_id, messages, tools, **kwargs)
        else:
            # Default to OpenAI-compatible
            logger.info(f"Unknown model prefix '{model_id}', trying OpenAI")
            return self._call_openai(model_id, messages, tools, **kwargs)

    def _call_openai(self, model: str, messages: List[Dict], tools: Any, **kwargs) -> Any:
        """Call OpenAI API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Install 'openai' package: pip install openai")

        client = OpenAI()

        call_kwargs = {"model": model, "messages": messages, **kwargs}
        if tools:
            call_kwargs["tools"] = tools

        return client.chat.completions.create(**call_kwargs)

    def _call_anthropic(self, model: str, messages: List[Dict], tools: Any, **kwargs) -> Any:
        """Call Anthropic API and convert response to OpenAI format."""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Install 'anthropic' package: pip install anthropic")

        client = Anthropic()

        # Convert messages (handle system message)
        system = None
        anthropic_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                anthropic_messages.append({"role": m["role"], "content": m["content"]})

        call_kwargs = {"model": model, "messages": anthropic_messages, "max_tokens": kwargs.pop("max_tokens", 4096)}
        if system:
            call_kwargs["system"] = system
        if tools:
            call_kwargs["tools"] = tools
        call_kwargs.update(kwargs)

        response = client.messages.create(**call_kwargs)

        # Convert to OpenAI format
        return self._anthropic_to_openai_response(response, model)

    def _call_google(self, model: str, messages: List[Dict], tools: Any, **kwargs) -> Any:
        """Call Google API and convert response to OpenAI format."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Install 'google-generativeai' package: pip install google-generativeai")

        # Configure if API key available
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

        # Convert messages to Google format
        model_name = model.replace("models/", "") if model.startswith("models/") else model
        gmodel = genai.GenerativeModel(model_name)

        # Simple conversion - concatenate messages
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        response = gmodel.generate_content(prompt)

        # Convert to OpenAI format
        return self._google_to_openai_response(response, model)

    def _anthropic_to_openai_response(self, response: Any, model: str) -> Any:
        """Convert Anthropic response to OpenAI format."""
        from types import SimpleNamespace

        content = ""
        if response.content:
            content = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])

        return SimpleNamespace(
            id=response.id,
            model=model,
            choices=[
                SimpleNamespace(
                    index=0,
                    message=SimpleNamespace(
                        role="assistant",
                        content=content,
                    ),
                    finish_reason=response.stop_reason,
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
        )

    def _google_to_openai_response(self, response: Any, model: str) -> Any:
        """Convert Google response to OpenAI format."""
        from types import SimpleNamespace
        import uuid

        content = response.text if hasattr(response, "text") else str(response)

        return SimpleNamespace(
            id=f"google-{uuid.uuid4().hex[:8]}",
            model=model,
            choices=[
                SimpleNamespace(
                    index=0,
                    message=SimpleNamespace(
                        role="assistant",
                        content=content,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=getattr(response, "usage_metadata", {}).get("prompt_token_count", 0),
                completion_tokens=getattr(response, "usage_metadata", {}).get("candidates_token_count", 0),
                total_tokens=getattr(response, "usage_metadata", {}).get("total_token_count", 0),
            ),
        )

    def as_langchain(self):
        """Return a LangChain-compatible chat model."""
        try:
            from kalibr_langchain.chat_model import KalibrChatModel
            return KalibrChatModel(router=self)
        except ImportError:
            raise ImportError("Install 'kalibr-langchain' package for LangChain integration")
