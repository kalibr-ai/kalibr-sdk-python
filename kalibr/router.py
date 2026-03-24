"""
Kalibr Router - Intelligent model routing with outcome learning.
"""

import os
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

from kalibr.provision import resolve_credentials
from opentelemetry import trace as otel_trace
from opentelemetry.trace import SpanContext, TraceFlags, NonRecordingSpan, set_span_in_context
from opentelemetry.context import Context

logger = logging.getLogger(__name__)

# Type for paths - either string or dict
PathSpec = Union[str, Dict[str, Any]]


def _create_context_with_trace_id(trace_id_hex: str) -> Optional[Context]:
    """Create an OTel context with a specific trace_id.

    This allows child spans to inherit the intelligence service's trace_id,
    enabling JOINs between outcomes and traces tables.
    """
    try:
        # Convert 32-char hex string to 128-bit int
        trace_id_int = int(trace_id_hex, 16)
        if trace_id_int == 0:
            return None

        # Create span context with our trace_id
        span_context = SpanContext(
            trace_id=trace_id_int,
            span_id=0xDEADBEEF,  # Placeholder, real span will have its own
            is_remote=True,  # Treat as remote parent so new span_id is generated
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )

        # Create a non-recording parent span and set in context
        parent_span = NonRecordingSpan(span_context)
        return set_span_in_context(parent_span)
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not create OTel context with trace_id: {e}")
        return None


class Router:
    """
    Routes LLM requests to the best model based on learned outcomes.

    Three scoring modes (in priority order):
    1. score_when: Continuous scoring (0.0-1.0). Best for quality optimization.
       Example: score_when=lambda out: min(1.0, len(out) / 500)
    2. success_when: Binary scoring (True/False). Good for pass/fail checks.
       Example: success_when=lambda out: "@" in out
    3. Default: When neither is provided, Kalibr auto-scores using heuristics
       (response length, structure, finish reason). Gives day-one metrics
       without any evaluation code.

    Examples:
        # Continuous scoring (best quality signal)
        router = Router(
            goal="summarize",
            paths=["gpt-4o", "claude-sonnet-4-20250514"],
            score_when=lambda out: min(1.0, len(out) / 500)
        )
        response = router.completion(messages=[...])

        # Binary auto-reporting
        router = Router(
            goal="extract_email",
            paths=["gpt-4o", "claude-sonnet-4-20250514"],
            success_when=lambda out: "@" in out
        )
        response = router.completion(messages=[...])
        # report() called automatically

        # Zero-config (default heuristic scoring)
        router = Router(
            goal="chat",
            paths=["gpt-4o", "claude-sonnet-4-20250514"]
        )
        response = router.completion(messages=[...])
        # Auto-scored using heuristics - no evaluation code needed

        # Manual reporting for complex validation
        router = Router(
            goal="book_meeting",
            paths=["gpt-4o", "claude-sonnet-4-20250514"]
        )
        response = router.completion(messages=[...])
        # ... complex validation logic ...
        router.report(success=meeting_booked)

    Warning:
        Router is not thread-safe. For concurrent requests, create separate
        Router instances per thread/task. For sequential requests in a single
        thread, Router can be reused across multiple completion() calls.
    """

    def __init__(
        self,
        goal: str,
        paths: Optional[List[PathSpec]] = None,
        success_when: Optional[Callable[[str], bool]] = None,
        score_when: Optional[Callable[[str], float]] = None,
        exploration_rate: Optional[float] = None,
        auto_register: bool = True,
    ):
        """
        Initialize router.

        Three scoring modes (in priority order):
        1. score_when: Continuous scoring (0.0-1.0). Best for quality optimization.
           Example: score_when=lambda out: min(1.0, len(out) / 500)
        2. success_when: Binary scoring (True/False). Good for pass/fail checks.
           Example: success_when=lambda out: "@" in out
        3. Default: When neither is provided, Kalibr auto-scores using heuristics
           (response length, structure, finish reason). Gives day-one metrics
           without any evaluation code.

        Args:
            goal: Name of the goal (e.g., "book_meeting", "summarize")
            paths: List of models or path configs. Examples:
                   ["gpt-4o", "claude-sonnet-4-20250514"]
                   [{"model": "gpt-4o", "tools": ["search"]}]
                   [{"model": "gpt-4o", "params": {"temperature": 0.7}}]
            success_when: Optional function to auto-evaluate success from LLM output.
                         Takes the output string and returns True/False.
                         When provided, report() is called automatically after completion().
                         Use for simple validations (output length, contains key string).
                         For complex validation (API calls, multi-step checks), omit this
                         and call report() manually.
                         Examples:
                             success_when=lambda out: len(out) > 0  # Not empty
                             success_when=lambda out: "@" in out     # Contains email
            score_when: Optional function to auto-evaluate quality from LLM output.
                       Takes the output string and returns a float (0.0-1.0).
                       Takes priority over success_when if both are provided.
                       Examples:
                           score_when=lambda out: min(1.0, len(out) / 500)
            exploration_rate: Override exploration rate (0.0-1.0)
            auto_register: If True, register paths on init
        """
        self.goal = goal

        # Validate required credentials
        api_key, tenant_id = resolve_credentials()

        if not api_key:
            raise ValueError(
                "No API key found. Set KALIBR_API_KEY or KALIBR_PROVISIONING_TOKEN.\n"
                "Get your API key from: https://dashboard.kalibr.systems/settings"
            )

        if not tenant_id:
            raise ValueError(
                "KALIBR_TENANT_ID environment variable not set.\n"
                "Find your Tenant ID at: https://dashboard.kalibr.systems/settings"
            )

        self.success_when = success_when
        self.score_when = score_when
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
            OpenAI-compatible ChatCompletion response with added attribute:
                - kalibr_trace_id: Trace ID for explicit outcome reporting
        """
        from kalibr.intelligence import decide

        # Reset state for new request
        self._outcome_reported = False

        # Step 1: Get routing decision FIRST (before creating span)
        decision = None
        model_id = None
        tool_id = None
        params = {}

        if force_model:
            model_id = force_model
            self._last_decision = {"model_id": model_id, "forced": True}
        else:
            try:
                decision = decide(goal=self.goal)
                model_id = decision.get("model_id") or self._paths[0]["model"]
                tool_id = decision.get("tool_id")
                params = decision.get("params") or {}
                self._last_decision = decision
            except Exception as e:
                logger.warning(f"Routing failed, using fallback: {e}")
                model_id = self._paths[0]["model"]
                tool_id = self._paths[0].get("tools")
                params = self._paths[0].get("params") or {}
                self._last_decision = {"model_id": model_id, "fallback": True, "error": str(e)}

        # Step 2: Determine trace_id
        decision_trace_id = self._last_decision.get("trace_id") if self._last_decision else None

        if decision_trace_id:
            trace_id = decision_trace_id
        else:
            trace_id = uuid.uuid4().hex  # Fallback: generate OTel-compatible format

        self._last_trace_id = trace_id
        self._last_model_id = model_id

        # Step 3: Create OTel context with intelligence trace_id
        otel_context = _create_context_with_trace_id(trace_id) if trace_id else None

        # Step 4: Create span with custom context (child spans inherit trace_id)
        tracer = otel_trace.get_tracer("kalibr.router")

        with tracer.start_as_current_span(
            "kalibr.router.completion",
            context=otel_context,
            attributes={
                "kalibr.goal": self.goal,
                "kalibr.trace_id": trace_id,
                "kalibr.model_id": model_id,
            }
        ) as router_span:
            # Add decision attributes
            if force_model:
                router_span.set_attribute("kalibr.forced", True)
            elif decision:
                router_span.set_attribute("kalibr.path_id", decision.get("path_id", ""))
                router_span.set_attribute("kalibr.reason", decision.get("reason", ""))
                router_span.set_attribute("kalibr.exploration", decision.get("exploration", False))
                router_span.set_attribute("kalibr.confidence", decision.get("confidence", 0.0))
            else:
                router_span.set_attribute("kalibr.fallback", True)

            # Step 5: Build ordered candidate paths for fallback
            # First: intelligence-selected path, then remaining registered paths
            candidate_paths = []
            selected_path = {"model": model_id, "tools": tool_id, "params": params}
            candidate_paths.append(selected_path)

            # Add remaining paths, skipping duplicates of the selected model
            for path in self._paths:
                if path["model"] != model_id:
                    candidate_paths.append(path)

            # Step 6: Try each candidate path with fallback
            from kalibr.intelligence import report_outcome

            last_exception = None
            for i, candidate in enumerate(candidate_paths):
                candidate_model = candidate["model"]
                candidate_tools = candidate.get("tools")
                candidate_params = candidate.get("params") or {}

                is_fallback = (i > 0)
                if is_fallback:
                    logger.warning(f"Primary path failed, trying fallback: {candidate_model}")

                try:
                    response = self._dispatch(
                        candidate_model,
                        messages,
                        candidate_tools,
                        **{**candidate_params, **kwargs}
                    )

                    # Success! Update state to reflect which model succeeded
                    self._last_model_id = candidate_model

                    # Auto-report if any scoring mechanism is provided (or use defaults)
                    if not self._outcome_reported:
                        try:
                            output = response.choices[0].message.content or ""

                            if self.score_when:
                                # Priority 1: User-provided continuous scorer
                                score = self.score_when(output)
                                score = min(1.0, max(0.0, float(score)))
                                self.report(success=score >= 0.5, score=score)
                            elif self.success_when:
                                # Priority 2: User-provided binary scorer
                                success = self.success_when(output)
                                self.report(success=success)
                            else:
                                # Priority 3: Default heuristic scoring (zero-config)
                                score = self._default_score(response)
                                self.report(success=score >= 0.5, score=score)
                        except Exception as e:
                            logger.warning(f"Auto-outcome evaluation failed: {e}")

                    # Add trace_id to response for explicit linkage
                    response.kalibr_trace_id = trace_id
                    return response

                except Exception as e:
                    last_exception = e

                    # Log the failure with model name and error
                    logger.warning(f"Model {candidate_model} failed: {type(e).__name__}: {e}")

                    # Report failure for this path to enable Thompson Sampling learning
                    try:
                        report_outcome(
                            trace_id=trace_id,
                            goal=self.goal,
                            success=False,
                            failure_reason=f"provider_error: {type(e).__name__}",
                            model_id=candidate_model,
                        )
                    except Exception:
                        pass

                    # Continue to next candidate
                    continue

            # All paths failed - set error attributes and raise
            router_span.set_attribute("error", True)
            router_span.set_attribute("error.type", type(last_exception).__name__)
            self._outcome_reported = True  # Prevent double-reporting on raise
            raise last_exception

    # Alias for common naming confusion
    complete = completion

    def execute(self, task: str, input_data: Any, **kwargs) -> Any:
        """Execute any ML task with intelligent routing.

        Args:
            task: HuggingFace task type ("automatic_speech_recognition", "text_to_image", etc.)
            input_data: Task-appropriate input (audio bytes, text prompt, etc.)
            **kwargs: Additional task-specific parameters

        Returns:
            Task-appropriate response (transcription text, PIL image, etc.)
        """
        from kalibr.intelligence import decide, report_outcome

        # Reset state for new request
        self._outcome_reported = False

        # Step 1: Get routing decision
        try:
            decision = decide(goal=self.goal)
            model_id = decision.get("model_id") or self._paths[0]["model"]
            self._last_decision = decision
        except Exception as e:
            logger.warning(f"Routing failed, using fallback: {e}")
            model_id = self._paths[0]["model"]
            self._last_decision = {"model_id": model_id, "fallback": True, "error": str(e)}

        # Step 2: Determine trace_id
        decision_trace_id = self._last_decision.get("trace_id") if self._last_decision else None
        trace_id = decision_trace_id or uuid.uuid4().hex
        self._last_trace_id = trace_id
        self._last_model_id = model_id

        # Step 3: Execute the task via HuggingFace Inference API
        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise ImportError("Install 'huggingface_hub' package: pip install huggingface_hub")

        client = InferenceClient()

        # Map task names to InferenceClient methods.
        # Must stay in sync with PATCHED_METHODS in huggingface_instr.py (all 17).
        task_method_map = {
            # Text
            "chat_completion": client.chat_completion,
            "text_generation": client.text_generation,
            "translation": client.translation,
            "summarization": client.summarization,
            "fill_mask": client.fill_mask,
            "table_question_answering": client.table_question_answering,
            # Audio
            "automatic_speech_recognition": client.automatic_speech_recognition,
            "text_to_speech": client.text_to_speech,
            "audio_classification": client.audio_classification,
            # Image
            "text_to_image": client.text_to_image,
            "image_to_text": client.image_to_text,
            "image_classification": client.image_classification,
            "image_segmentation": client.image_segmentation,
            "object_detection": client.object_detection,
            # Embedding
            "feature_extraction": client.feature_extraction,
            # Classification
            "text_classification": client.text_classification,
            "token_classification": client.token_classification,
        }

        method = task_method_map.get(task)
        if method is None:
            raise ValueError(
                f"Unsupported task '{task}'. Supported tasks: {', '.join(sorted(task_method_map.keys()))}"
            )

        try:
            response = method(input_data, model=model_id, **kwargs)
        except Exception as e:
            # Report failure
            try:
                report_outcome(
                    trace_id=trace_id,
                    goal=self.goal,
                    success=False,
                    failure_reason=f"provider_error: {type(e).__name__}",
                    model_id=model_id,
                )
            except Exception:
                pass
            self._outcome_reported = True
            raise

        # Step 4: Score and report
        if not self._outcome_reported:
            try:
                if self.score_when:
                    score = self.score_when(response)
                    score = min(1.0, max(0.0, float(score)))
                    self.report(success=score >= 0.5, score=score)
                elif self.success_when:
                    success = self.success_when(response)
                    self.report(success=success)
                else:
                    score = self._default_score(response)
                    self.report(success=score >= 0.5, score=score)
            except Exception as e:
                logger.warning(f"Auto-outcome evaluation failed: {e}")

        return response

    def _default_score(self, response) -> float:
        """
        Compute a heuristic quality score from an LLM response.
        Used when no success_when or score_when is provided.
        Gives users day-one quality metrics without writing evaluation code.

        Handles multiple response types:
        - Chat completion (has .choices[0].message.content) -> text heuristics
        - bytes (audio) -> 1.0 if non-empty
        - Transcription (has .text attribute) -> text heuristics on .text
        - PIL.Image -> 1.0 if not None
        - Other -> 0.5 (neutral, let user-provided scorer handle it)

        Signals for text scoring (all normalized to 0-1, then weighted average):
        - non_empty: 1.0 if response has content, 0.0 if empty
        - length_score: normalized response length (sigmoid around 200 chars)
        - structure_score: bonus for JSON validity, markdown headers, bullet points
        - finish_reason_score: 1.0 for "stop", 0.5 for "length" (truncated), 0.0 for error
        """
        # Handle bytes (e.g., audio output)
        if isinstance(response, bytes):
            return 1.0 if len(response) > 0 else 0.0

        # Handle PIL.Image
        try:
            from PIL import Image
            if isinstance(response, Image.Image):
                return 1.0
        except ImportError:
            pass

        # Handle transcription-style responses (has .text but no .choices)
        if hasattr(response, "text") and not hasattr(response, "choices"):
            content = response.text or ""
            return self._score_text_content(content)

        # Handle chat completion responses
        try:
            content = response.choices[0].message.content or ""
        except (AttributeError, IndexError):
            # Unknown response type - return neutral score
            if response is None:
                return 0.0
            return 0.5

        return self._score_text_content(content, response)

    def _score_text_content(self, content: str, response: Any = None) -> float:
        """Score text content using heuristics. Used by _default_score for text-based responses."""
        # Signal 1: Non-empty (binary)
        non_empty = 1.0 if len(content.strip()) > 0 else 0.0
        if non_empty == 0.0:
            return 0.0  # Empty response is always 0

        # Signal 2: Response length (sigmoid - most responses 50-2000 chars)
        import math
        char_count = len(content)
        # Sigmoid centered at 200 chars, gives ~0.5 at 200, ~0.95 at 1000
        length_score = 1.0 / (1.0 + math.exp(-0.005 * (char_count - 200)))

        # Signal 3: Structure (JSON, markdown, lists indicate structured output)
        structure_score = 0.5  # baseline
        content_stripped = content.strip()
        # JSON detection
        if (content_stripped.startswith('{') and content_stripped.endswith('}')) or \
           (content_stripped.startswith('[') and content_stripped.endswith(']')):
            try:
                import json
                json.loads(content_stripped)
                structure_score = 1.0  # Valid JSON
            except (json.JSONDecodeError, ValueError):
                structure_score = 0.3  # Looks like JSON but invalid
        # Markdown/list detection
        elif any(marker in content for marker in ['## ', '- ', '* ', '1. ', '```']):
            structure_score = 0.8

        # Signal 4: Finish reason
        finish_score = 0.5  # default when no response object
        if response is not None:
            try:
                finish_reason = response.choices[0].finish_reason
                if finish_reason == "stop":
                    finish_score = 1.0
                elif finish_reason == "length":
                    finish_score = 0.5  # Truncated
                else:
                    finish_score = 0.3  # Unknown/error
            except (AttributeError, IndexError):
                finish_score = 0.5

        # Weighted average
        score = (
            non_empty * 0.1 +
            length_score * 0.3 +
            structure_score * 0.3 +
            finish_score * 0.3
        )

        return round(min(1.0, max(0.0, score)), 3)

    def report(
        self,
        success: bool,
        reason: Optional[str] = None,
        score: Optional[float] = None,
        trace_id: Optional[str] = None,
        failure_category: Optional[str] = None,
    ):
        """
        Report outcome for the last completion.

        Args:
            success: Whether the task succeeded
            reason: Optional failure reason
            score: Optional quality score (0.0-1.0)
            trace_id: Optional explicit trace ID (uses last completion's trace_id if not provided)
            failure_category: Optional structured failure category for clustering
        """
        if self._outcome_reported:
            logger.warning("Outcome already reported for this completion. Each completion() requires a separate report() call.")
            return

        if failure_category is not None:
            from kalibr.intelligence import FAILURE_CATEGORIES
            if failure_category not in FAILURE_CATEGORIES:
                raise ValueError(
                    f"Invalid failure_category '{failure_category}'. "
                    f"Must be one of: {', '.join(FAILURE_CATEGORIES)}"
                )

        from kalibr.intelligence import report_outcome

        trace_id = trace_id or self._last_trace_id
        if not trace_id:
            raise ValueError("Must call completion() before report(). No trace_id available.")

        try:
            report_outcome(
                trace_id=trace_id,
                goal=self.goal,
                success=success,
                score=score,
                failure_reason=reason,
                failure_category=failure_category,
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
        elif "/" in model_id and not model_id.startswith(("models/", "ft:")):
            # org/model format = HuggingFace
            return self._call_huggingface(model_id, messages, tools, **kwargs)
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
        # Note: tools parameter from path config is for Kalibr routing only.
        # Users can pass actual tool definitions via **kwargs if needed.

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
        # Note: tools parameter from path config is for Kalibr routing only.
        # Users can pass actual tool definitions via **kwargs if needed.
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

    def _call_huggingface(self, model: str, messages: List[Dict], tools: Any, **kwargs) -> Any:
        """Call HuggingFace Inference API and convert response to OpenAI format."""
        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise ImportError("Install 'huggingface_hub' package: pip install huggingface_hub")

        client = InferenceClient()

        call_kwargs = {"model": model, "messages": messages, **kwargs}

        response = client.chat.completions.create(**call_kwargs)

        return self._huggingface_to_openai_response(response, model)

    def _huggingface_to_openai_response(self, response: Any, model: str) -> Any:
        """Convert HuggingFace chat completion response to OpenAI format."""
        from types import SimpleNamespace

        # HuggingFace chat completions return OpenAI-compatible format,
        # but normalize to SimpleNamespace for consistent attribute access
        choices = []
        for choice in response.choices:
            choices.append(SimpleNamespace(
                index=choice.index,
                message=SimpleNamespace(
                    role=choice.message.role,
                    content=choice.message.content or "",
                ),
                finish_reason=getattr(choice, "finish_reason", "stop"),
            ))

        usage_obj = getattr(response, "usage", None)
        return SimpleNamespace(
            id=getattr(response, "id", f"hf-{model}"),
            model=model,
            choices=choices,
            usage=SimpleNamespace(
                prompt_tokens=getattr(usage_obj, "prompt_tokens", 0),
                completion_tokens=getattr(usage_obj, "completion_tokens", 0),
                total_tokens=getattr(usage_obj, "total_tokens", 0),
            ),
        )

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

    def __getattr__(self, name):
        suggestions = {
            "predict": "completion",
            "generate": "completion",
            "chat": "completion",
            "invoke": "completion",
            "run": "completion",
        }
        if name in suggestions:
            raise AttributeError(
                f"Router has no method '{name}'. Did you mean '{suggestions[name]}()'?"
            )
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def as_langchain(self):
        """Return a LangChain-compatible chat model."""
        try:
            from kalibr_langchain.chat_model import KalibrChatModel
            return KalibrChatModel(router=self)
        except ImportError:
            raise ImportError("Install 'kalibr-langchain' package for LangChain integration")
