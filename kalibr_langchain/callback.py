"""Kalibr Callback Handler for LangChain.

This module provides the main callback handler that integrates LangChain
with Kalibr's observability platform.
"""

import atexit
import hashlib
import hmac
import os
import queue
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

import httpx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, Generation, LLMResult

# Import Kalibr cost adapters
try:
    from kalibr.cost_adapter import CostAdapterFactory
except ImportError:
    CostAdapterFactory = None

from kalibr.context import get_goal

# Import tiktoken for token counting
try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


def _count_tokens(text: str, model: str) -> int:
    """Count tokens for given text and model."""
    if not text:
        return 0

    if HAS_TIKTOKEN and "gpt" in model.lower():
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            pass

    # Fallback: approximate (1 token ~= 4 chars)
    return len(text) // 4


def _get_provider_from_model(model: str) -> str:
    """Infer provider from model name."""
    model_lower = model.lower()

    if any(x in model_lower for x in ["gpt", "text-davinci", "text-embedding", "whisper", "dall-e"]):
        return "openai"
    elif any(x in model_lower for x in ["claude"]):
        return "anthropic"
    elif any(x in model_lower for x in ["gemini", "palm", "bison"]):
        return "google"
    elif any(x in model_lower for x in ["cohere", "command"]):
        return "cohere"
    else:
        return "custom"


def _serialize_for_metadata(obj: Any) -> Any:
    """Serialize objects for JSON metadata."""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_metadata(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _serialize_for_metadata(v) for k, v in obj.items()}
    elif hasattr(obj, "dict"):
        return obj.dict()
    elif hasattr(obj, "__dict__"):
        return {k: _serialize_for_metadata(v) for k, v in obj.__dict__.items()
                if not k.startswith("_")}
    else:
        return str(obj)


class SpanTracker:
    """Tracks active spans and their metadata."""

    def __init__(self):
        self.spans: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start_span(
        self,
        run_id: str,
        trace_id: str,
        parent_run_id: Optional[str],
        operation: str,
        span_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Start a new span."""
        span_id = str(uuid.uuid4())

        with self._lock:
            parent_span_id = None
            if parent_run_id and parent_run_id in self.spans:
                parent_span_id = self.spans[parent_run_id].get("span_id")

            span = {
                "span_id": span_id,
                "trace_id": trace_id,
                "parent_span_id": parent_span_id,
                "operation": operation,
                "span_type": span_type,
                "ts_start": datetime.now(timezone.utc),
                "status": "success",
                **kwargs
            }
            self.spans[run_id] = span
            return span

    def end_span(self, run_id: str) -> Optional[Dict[str, Any]]:
        """End a span and return its data."""
        with self._lock:
            if run_id in self.spans:
                span = self.spans.pop(run_id)
                span["ts_end"] = datetime.now(timezone.utc)
                span["duration_ms"] = int(
                    (span["ts_end"] - span["ts_start"]).total_seconds() * 1000
                )
                return span
            return None

    def update_span(self, run_id: str, **kwargs):
        """Update span with additional data."""
        with self._lock:
            if run_id in self.spans:
                self.spans[run_id].update(kwargs)

    def get_span(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get span data."""
        with self._lock:
            return self.spans.get(run_id)


class KalibrCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler for Kalibr observability.

    This handler captures telemetry from LangChain components and sends
    them to the Kalibr backend for analysis and visualization.

    Supported callbacks:
    - LLM start/end/error
    - Chat model start/end
    - Chain start/end/error
    - Tool start/end/error
    - Agent action/finish
    - Retriever start/end
    - Text generation (streaming)

    Args:
        api_key: Kalibr API key (or KALIBR_API_KEY env var)
        endpoint: Backend endpoint URL (or KALIBR_ENDPOINT env var)
        tenant_id: Tenant identifier (or KALIBR_TENANT_ID env var)
        environment: Environment name (or KALIBR_ENVIRONMENT env var)
        service: Service name (or KALIBR_SERVICE env var)
        workflow_id: Workflow identifier for grouping traces
        secret: HMAC secret for request signing
        batch_size: Max events per batch (default: 100)
        flush_interval: Flush interval in seconds (default: 2.0)
        capture_input: Whether to capture input prompts (default: True)
        capture_output: Whether to capture outputs (default: True)
        max_content_length: Max length for captured content (default: 10000)
        metadata: Additional metadata to include in all events
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None,
        environment: Optional[str] = None,
        service: Optional[str] = None,
        workflow_id: Optional[str] = None,
        secret: Optional[str] = None,
        batch_size: int = 100,
        flush_interval: float = 2.0,
        capture_input: bool = True,
        capture_output: bool = True,
        max_content_length: int = 10000,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()

        # Configuration
        self.api_key = api_key or os.getenv("KALIBR_API_KEY", "")
        self.endpoint = endpoint or os.getenv(
            "KALIBR_ENDPOINT",
            os.getenv("KALIBR_API_ENDPOINT", "https://api.kalibr.systems/api/v1/traces")
        )
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "default")
        self.environment = environment or os.getenv("KALIBR_ENVIRONMENT", "prod")
        self.service = service or os.getenv("KALIBR_SERVICE", "langchain-app")
        self.workflow_id = workflow_id or os.getenv("KALIBR_WORKFLOW_ID", "default-workflow")
        self.secret = secret

        # Content capture settings
        self.capture_input = capture_input
        self.capture_output = capture_output
        self.max_content_length = max_content_length
        self.default_metadata = metadata or {}

        # Batching configuration
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Span tracking
        self._span_tracker = SpanTracker()

        # Root trace ID (created per top-level chain/llm call)
        self._root_trace_id: Optional[str] = None
        self._trace_lock = threading.Lock()

        # Event queue for batching
        self._event_queue: queue.Queue = queue.Queue(maxsize=5000)

        # HTTP client
        self._client = httpx.Client(timeout=10.0)

        # Background flusher thread
        self._shutdown = False
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        # Register cleanup
        atexit.register(self.shutdown)

    def _get_or_create_trace_id(self, parent_run_id: Optional[str]) -> str:
        """Get existing trace ID or create a new one for root spans."""
        with self._trace_lock:
            if parent_run_id is None:
                # This is a root span, create new trace
                self._root_trace_id = str(uuid.uuid4())
            return self._root_trace_id or str(uuid.uuid4())

    def _truncate(self, text: str) -> str:
        """Truncate text to max length."""
        if len(text) > self.max_content_length:
            return text[:self.max_content_length] + "...[truncated]"
        return text

    def _compute_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Compute cost using Kalibr cost adapters."""
        if CostAdapterFactory is not None:
            return CostAdapterFactory.compute_cost(
                vendor=provider,
                model_name=model,
                tokens_in=input_tokens,
                tokens_out=output_tokens
            )
        return 0.0

    def _create_event(
        self,
        span: Dict[str, Any],
        input_tokens: int = 0,
        output_tokens: int = 0,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a standardized trace event from span data."""
        provider = span.get("provider", "custom")
        model = span.get("model", "unknown")

        # Compute cost
        cost_usd = self._compute_cost(provider, model, input_tokens, output_tokens)

        # Extract tool_id from operation if this is a tool span
        tool_id = ""
        tool_input = ""
        tool_output = ""

        if span.get("span_type") == "tool":
            operation = span.get("operation", "")
            if operation.startswith("tool:"):
                tool_id = operation[5:]  # Extract "browserless" from "tool:browserless"

            # Get tool input/output from span (truncate to 10KB)
            if span.get("input"):
                tool_input = str(span["input"])[:10000]
            if metadata and metadata.get("output"):
                tool_output = str(metadata["output"])[:10000]

        # Get goal from context (thread-safe)
        current_goal = get_goal() or ""

        # Build event
        event = {
            "schema_version": "1.0",
            "trace_id": span["trace_id"],
            "span_id": span["span_id"],
            "parent_span_id": span.get("parent_span_id"),
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "provider": provider,
            "model_id": model,
            "model_name": model,
            "operation": span["operation"],
            "endpoint": span.get("endpoint", span["operation"]),
            "duration_ms": span.get("duration_ms", 0),
            "latency_ms": span.get("duration_ms", 0),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost_usd,
            "total_cost_usd": cost_usd,
            "status": span.get("status", "success"),
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": span["ts_start"].isoformat(),
            "ts_start": span["ts_start"].isoformat(),
            "ts_end": span.get("ts_end", datetime.now(timezone.utc)).isoformat(),
            "environment": self.environment,
            "service": self.service,
            "runtime_env": os.getenv("RUNTIME_ENV", "local"),
            "sandbox_id": os.getenv("SANDBOX_ID", "local"),
            # New fields for tool/goal tracking
            "tool_id": tool_id,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "goal": current_goal,
            "metadata": {
                **self.default_metadata,
                "span_type": span.get("span_type", "llm"),
                "langchain": True,
                **(metadata or {}),
            },
        }

        return event

    def _enqueue_event(self, event: Dict[str, Any]):
        """Add event to queue for batching."""
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            # Drop oldest event and retry
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except:
                pass

    def _flush_loop(self):
        """Background thread to flush events periodically."""
        batch = []
        last_flush = time.time()

        while not self._shutdown:
            try:
                try:
                    event = self._event_queue.get(timeout=0.1)
                    batch.append(event)
                except queue.Empty:
                    pass

                now = time.time()
                should_flush = (
                    len(batch) >= self.batch_size or
                    (batch and now - last_flush >= self.flush_interval)
                )

                if should_flush:
                    self._send_batch(batch)
                    batch = []
                    last_flush = now

            except Exception:
                pass

        # Final flush on shutdown
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Send batch to Kalibr backend."""
        if not batch:
            return

        try:
            payload = {"events": batch}

            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            if self.secret:
                import json
                body = json.dumps(payload).encode("utf-8")
                signature = hmac.new(
                    self.secret.encode(), body, hashlib.sha256
                ).hexdigest()
                headers["X-Signature"] = signature

            response = self._client.post(
                self.endpoint,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

        except Exception as e:
            # Log error but don't raise
            pass

    def shutdown(self):
        """Shutdown handler and flush remaining events."""
        if self._shutdown:
            return

        self._shutdown = True

        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)

        self._client.close()

    # =========================================================================
    # LLM Callbacks
    # =========================================================================

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts generating."""
        run_id_str = str(run_id)
        parent_id_str = str(parent_run_id) if parent_run_id else None
        trace_id = self._get_or_create_trace_id(parent_id_str)

        # Extract model info
        model = kwargs.get("invocation_params", {}).get("model_name", "unknown")
        if model == "unknown":
            model = serialized.get("kwargs", {}).get("model_name", "unknown")

        provider = _get_provider_from_model(model)

        # Calculate input tokens
        prompt_text = "\n".join(prompts)
        input_tokens = _count_tokens(prompt_text, model)

        span_metadata = {
            "tags": tags or [],
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
        }

        if self.capture_input:
            span_metadata["input"] = self._truncate(prompt_text)

        self._span_tracker.start_span(
            run_id=run_id_str,
            trace_id=trace_id,
            parent_run_id=parent_id_str,
            operation="llm_call",
            span_type="llm",
            model=model,
            provider=provider,
            endpoint=f"{provider}.{model}",
            **span_metadata,
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM finishes generating."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        # Extract token usage from response
        input_tokens = span.get("input_tokens", 0)
        output_tokens = 0
        output_text = ""

        # Get token usage from LLM response
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", input_tokens)
                output_tokens = token_usage.get("completion_tokens", 0)

        # Extract output text
        if response.generations:
            output_parts = []
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, "text"):
                        output_parts.append(gen.text)
                    elif hasattr(gen, "message") and hasattr(gen.message, "content"):
                        output_parts.append(gen.message.content)
            output_text = "\n".join(output_parts)

            # Fallback token count from output
            if output_tokens == 0:
                output_tokens = _count_tokens(output_text, span.get("model", "unknown"))

        # Build metadata
        event_metadata = {
            "tags": span.get("tags", []),
        }
        if self.capture_output and output_text:
            event_metadata["output"] = self._truncate(output_text)
        if self.capture_input and "input" in span:
            event_metadata["input"] = span["input"]

        event = self._create_event(
            span=span,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=event_metadata,
        )

        self._enqueue_event(event)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when LLM errors."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        span["status"] = "error"

        event = self._create_event(
            span=span,
            input_tokens=span.get("input_tokens", 0),
            output_tokens=0,
            error_type=type(error).__name__,
            error_message=str(error)[:512],
            metadata={
                "tags": span.get("tags", []),
                "stack_trace": "".join(traceback.format_exception(
                    type(error), error, error.__traceback__
                ))[:2000],
            },
        )

        self._enqueue_event(event)

    # =========================================================================
    # Chat Model Callbacks
    # =========================================================================

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chat model starts."""
        run_id_str = str(run_id)
        parent_id_str = str(parent_run_id) if parent_run_id else None
        trace_id = self._get_or_create_trace_id(parent_id_str)

        # Extract model info
        model = kwargs.get("invocation_params", {}).get("model", "unknown")
        if model == "unknown":
            model = kwargs.get("invocation_params", {}).get("model_name", "unknown")
        if model == "unknown":
            model = serialized.get("kwargs", {}).get("model", "unknown")
        if model == "unknown":
            model = serialized.get("kwargs", {}).get("model_name", "unknown")

        provider = _get_provider_from_model(model)

        # Calculate input tokens from messages
        message_text = ""
        for msg_list in messages:
            for msg in msg_list:
                if hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, str):
                        message_text += content + "\n"
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, str):
                                message_text += item + "\n"
                            elif isinstance(item, dict) and "text" in item:
                                message_text += item["text"] + "\n"

        input_tokens = _count_tokens(message_text, model)

        span_metadata = {
            "tags": tags or [],
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "message_count": sum(len(msg_list) for msg_list in messages),
        }

        if self.capture_input:
            span_metadata["input"] = self._truncate(message_text)

        self._span_tracker.start_span(
            run_id=run_id_str,
            trace_id=trace_id,
            parent_run_id=parent_id_str,
            operation="chat_completion",
            span_type="chat",
            model=model,
            provider=provider,
            endpoint=f"{provider}.chat.completions",
            **span_metadata,
        )

    # =========================================================================
    # Chain Callbacks
    # =========================================================================

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain starts."""
        run_id_str = str(run_id)
        parent_id_str = str(parent_run_id) if parent_run_id else None
        trace_id = self._get_or_create_trace_id(parent_id_str)

        # Get chain name
        chain_name = serialized.get("name", serialized.get("id", ["unknown"])[-1])

        span_metadata = {
            "tags": tags or [],
            "chain_name": chain_name,
        }

        if self.capture_input:
            input_str = str(_serialize_for_metadata(inputs))
            span_metadata["input"] = self._truncate(input_str)

        self._span_tracker.start_span(
            run_id=run_id_str,
            trace_id=trace_id,
            parent_run_id=parent_id_str,
            operation=f"chain:{chain_name}",
            span_type="chain",
            model="chain",
            provider="langchain",
            endpoint=chain_name,
            **span_metadata,
        )

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain ends."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        event_metadata = {
            "tags": span.get("tags", []),
            "chain_name": span.get("chain_name", "unknown"),
        }

        if self.capture_output:
            output_str = str(_serialize_for_metadata(outputs))
            event_metadata["output"] = self._truncate(output_str)
        if self.capture_input and "input" in span:
            event_metadata["input"] = span["input"]

        event = self._create_event(
            span=span,
            metadata=event_metadata,
        )

        self._enqueue_event(event)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when chain errors."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        span["status"] = "error"

        event = self._create_event(
            span=span,
            error_type=type(error).__name__,
            error_message=str(error)[:512],
            metadata={
                "tags": span.get("tags", []),
                "chain_name": span.get("chain_name", "unknown"),
                "stack_trace": "".join(traceback.format_exception(
                    type(error), error, error.__traceback__
                ))[:2000],
            },
        )

        self._enqueue_event(event)

    # =========================================================================
    # Tool Callbacks
    # =========================================================================

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool starts."""
        run_id_str = str(run_id)
        parent_id_str = str(parent_run_id) if parent_run_id else None
        trace_id = self._get_or_create_trace_id(parent_id_str)

        tool_name = serialized.get("name", "unknown_tool")

        span_metadata = {
            "tags": tags or [],
            "tool_name": tool_name,
        }

        if self.capture_input:
            span_metadata["input"] = self._truncate(input_str)

        self._span_tracker.start_span(
            run_id=run_id_str,
            trace_id=trace_id,
            parent_run_id=parent_id_str,
            operation=f"tool:{tool_name}",
            span_type="tool",
            model="tool",
            provider="langchain",
            endpoint=tool_name,
            **span_metadata,
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool ends."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        event_metadata = {
            "tags": span.get("tags", []),
            "tool_name": span.get("tool_name", "unknown"),
        }

        if self.capture_output:
            output_str = str(_serialize_for_metadata(output))
            event_metadata["output"] = self._truncate(output_str)
        if self.capture_input and "input" in span:
            event_metadata["input"] = span["input"]

        event = self._create_event(
            span=span,
            metadata=event_metadata,
        )

        self._enqueue_event(event)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when tool errors."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        span["status"] = "error"

        event = self._create_event(
            span=span,
            error_type=type(error).__name__,
            error_message=str(error)[:512],
            metadata={
                "tags": span.get("tags", []),
                "tool_name": span.get("tool_name", "unknown"),
                "stack_trace": "".join(traceback.format_exception(
                    type(error), error, error.__traceback__
                ))[:2000],
            },
        )

        self._enqueue_event(event)

    # =========================================================================
    # Agent Callbacks
    # =========================================================================

    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent takes an action."""
        # Agent actions are tracked as part of the chain
        # We just update metadata on the parent span
        parent_id_str = str(parent_run_id) if parent_run_id else None
        if parent_id_str:
            self._span_tracker.update_span(
                parent_id_str,
                last_action=action.tool,
                last_action_input=self._truncate(str(action.tool_input))
                if self.capture_input else None,
            )

    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
        # Agent finish is tracked as part of the chain
        parent_id_str = str(parent_run_id) if parent_run_id else None
        if parent_id_str:
            self._span_tracker.update_span(
                parent_id_str,
                agent_finish=True,
                return_values=self._truncate(str(finish.return_values))
                if self.capture_output else None,
            )

    # =========================================================================
    # Retriever Callbacks
    # =========================================================================

    def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever starts."""
        run_id_str = str(run_id)
        parent_id_str = str(parent_run_id) if parent_run_id else None
        trace_id = self._get_or_create_trace_id(parent_id_str)

        retriever_name = serialized.get("name", serialized.get("id", ["unknown"])[-1])

        span_metadata = {
            "tags": tags or [],
            "retriever_name": retriever_name,
        }

        if self.capture_input:
            span_metadata["query"] = self._truncate(query)

        self._span_tracker.start_span(
            run_id=run_id_str,
            trace_id=trace_id,
            parent_run_id=parent_id_str,
            operation=f"retriever:{retriever_name}",
            span_type="retriever",
            model="retriever",
            provider="langchain",
            endpoint=retriever_name,
            **span_metadata,
        )

    def on_retriever_end(
        self,
        documents: Sequence[Document],
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever ends."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        event_metadata = {
            "tags": span.get("tags", []),
            "retriever_name": span.get("retriever_name", "unknown"),
            "document_count": len(documents),
        }

        if self.capture_input and "query" in span:
            event_metadata["query"] = span["query"]

        if self.capture_output and documents:
            # Capture document summaries
            doc_summaries = []
            for doc in documents[:5]:  # Limit to first 5 docs
                summary = {
                    "content_preview": self._truncate(doc.page_content[:200]),
                    "metadata": _serialize_for_metadata(doc.metadata),
                }
                doc_summaries.append(summary)
            event_metadata["documents"] = doc_summaries

        event = self._create_event(
            span=span,
            metadata=event_metadata,
        )

        self._enqueue_event(event)

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever errors."""
        run_id_str = str(run_id)
        span = self._span_tracker.end_span(run_id_str)

        if not span:
            return

        span["status"] = "error"

        event = self._create_event(
            span=span,
            error_type=type(error).__name__,
            error_message=str(error)[:512],
            metadata={
                "tags": span.get("tags", []),
                "retriever_name": span.get("retriever_name", "unknown"),
                "stack_trace": "".join(traceback.format_exception(
                    type(error), error, error.__traceback__
                ))[:2000],
            },
        )

        self._enqueue_event(event)

    # =========================================================================
    # Text/Streaming Callbacks
    # =========================================================================

    def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called on each new token during streaming."""
        # We track tokens but don't send events for each one
        run_id_str = str(run_id)
        span = self._span_tracker.get_span(run_id_str)

        if span:
            current_tokens = span.get("streaming_tokens", "")
            self._span_tracker.update_span(
                run_id_str,
                streaming_tokens=current_tokens + token,
            )

    def on_text(
        self,
        text: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when text is generated."""
        # Track text generation
        pass

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def flush(self):
        """Force flush all pending events."""
        events = []
        while True:
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except queue.Empty:
                break

        if events:
            self._send_batch(events)

    def get_trace_id(self) -> Optional[str]:
        """Get current trace ID."""
        return self._root_trace_id
