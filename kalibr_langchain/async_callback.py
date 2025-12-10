"""Async Kalibr Callback Handler for LangChain.

This module provides an async-compatible callback handler for use with
async LangChain operations.
"""

import asyncio
import os
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

import httpx
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from .callback import (
    SpanTracker,
    _count_tokens,
    _get_provider_from_model,
    _serialize_for_metadata,
    CostAdapterFactory,
)


class AsyncKalibrCallbackHandler(AsyncCallbackHandler):
    """Async LangChain callback handler for Kalibr observability.

    This handler is designed for async LangChain operations and uses
    async HTTP calls to send telemetry.

    Args:
        api_key: Kalibr API key (or KALIBR_API_KEY env var)
        endpoint: Backend endpoint URL (or KALIBR_ENDPOINT env var)
        tenant_id: Tenant identifier (or KALIBR_TENANT_ID env var)
        environment: Environment name (or KALIBR_ENVIRONMENT env var)
        service: Service name (or KALIBR_SERVICE env var)
        workflow_id: Workflow identifier for grouping traces
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

        # Content capture settings
        self.capture_input = capture_input
        self.capture_output = capture_output
        self.max_content_length = max_content_length
        self.default_metadata = metadata or {}

        # Span tracking
        self._span_tracker = SpanTracker()

        # Root trace ID
        self._root_trace_id: Optional[str] = None
        self._trace_lock = asyncio.Lock()

        # Async HTTP client
        self._client: Optional[httpx.AsyncClient] = None

        # Event buffer for batching
        self._event_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def _get_or_create_trace_id(self, parent_run_id: Optional[str]) -> str:
        """Get existing trace ID or create a new one for root spans."""
        async with self._trace_lock:
            if parent_run_id is None:
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

        cost_usd = self._compute_cost(provider, model, input_tokens, output_tokens)

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
            "metadata": {
                **self.default_metadata,
                "span_type": span.get("span_type", "llm"),
                "langchain": True,
                "async": True,
                **(metadata or {}),
            },
        }

        return event

    async def _send_event(self, event: Dict[str, Any]):
        """Send a single event to Kalibr backend."""
        async with self._buffer_lock:
            self._event_buffer.append(event)

            # Flush if buffer is large enough
            if len(self._event_buffer) >= 10:
                await self._flush_buffer()

    async def _flush_buffer(self):
        """Flush event buffer to backend."""
        if not self._event_buffer:
            return

        events = self._event_buffer.copy()
        self._event_buffer.clear()

        try:
            client = await self._get_client()
            payload = {"events": events}

            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            await client.post(
                self.endpoint,
                json=payload,
                headers=headers,
            )
        except Exception:
            # Log error but don't raise
            pass

    async def close(self):
        """Close the handler and flush remaining events."""
        async with self._buffer_lock:
            await self._flush_buffer()

        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # LLM Callbacks
    # =========================================================================

    async def on_llm_start(
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
        trace_id = await self._get_or_create_trace_id(parent_id_str)

        model = kwargs.get("invocation_params", {}).get("model_name", "unknown")
        if model == "unknown":
            model = serialized.get("kwargs", {}).get("model_name", "unknown")

        provider = _get_provider_from_model(model)

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

    async def on_llm_end(
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

        input_tokens = span.get("input_tokens", 0)
        output_tokens = 0
        output_text = ""

        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", input_tokens)
                output_tokens = token_usage.get("completion_tokens", 0)

        if response.generations:
            output_parts = []
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, "text"):
                        output_parts.append(gen.text)
                    elif hasattr(gen, "message") and hasattr(gen.message, "content"):
                        output_parts.append(gen.message.content)
            output_text = "\n".join(output_parts)

            if output_tokens == 0:
                output_tokens = _count_tokens(output_text, span.get("model", "unknown"))

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

        await self._send_event(event)

    async def on_llm_error(
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

        await self._send_event(event)

    # =========================================================================
    # Chat Model Callbacks
    # =========================================================================

    async def on_chat_model_start(
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
        trace_id = await self._get_or_create_trace_id(parent_id_str)

        model = kwargs.get("invocation_params", {}).get("model", "unknown")
        if model == "unknown":
            model = kwargs.get("invocation_params", {}).get("model_name", "unknown")
        if model == "unknown":
            model = serialized.get("kwargs", {}).get("model", "unknown")

        provider = _get_provider_from_model(model)

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

    async def on_chain_start(
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
        trace_id = await self._get_or_create_trace_id(parent_id_str)

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

    async def on_chain_end(
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

        await self._send_event(event)

    async def on_chain_error(
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

        await self._send_event(event)

    # =========================================================================
    # Tool Callbacks
    # =========================================================================

    async def on_tool_start(
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
        trace_id = await self._get_or_create_trace_id(parent_id_str)

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

    async def on_tool_end(
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

        await self._send_event(event)

    async def on_tool_error(
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

        await self._send_event(event)

    # =========================================================================
    # Agent Callbacks
    # =========================================================================

    async def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent takes an action."""
        parent_id_str = str(parent_run_id) if parent_run_id else None
        if parent_id_str:
            self._span_tracker.update_span(
                parent_id_str,
                last_action=action.tool,
                last_action_input=self._truncate(str(action.tool_input))
                if self.capture_input else None,
            )

    async def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when agent finishes."""
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

    async def on_retriever_start(
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
        trace_id = await self._get_or_create_trace_id(parent_id_str)

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

    async def on_retriever_end(
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
            doc_summaries = []
            for doc in documents[:5]:
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

        await self._send_event(event)

    async def on_retriever_error(
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

        await self._send_event(event)

    # =========================================================================
    # Streaming Callbacks
    # =========================================================================

    async def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called on each new token during streaming."""
        run_id_str = str(run_id)
        span = self._span_tracker.get_span(run_id_str)

        if span:
            current_tokens = span.get("streaming_tokens", "")
            self._span_tracker.update_span(
                run_id_str,
                streaming_tokens=current_tokens + token,
            )

    async def on_text(
        self,
        text: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called when text is generated."""
        pass

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def flush(self):
        """Force flush all pending events."""
        async with self._buffer_lock:
            await self._flush_buffer()

    def get_trace_id(self) -> Optional[str]:
        """Get current trace ID."""
        return self._root_trace_id
