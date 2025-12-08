"""Kalibr Callbacks for CrewAI.

This module provides callback classes for CrewAI agents and tasks.
"""

import atexit
import os
import queue
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

# Import Kalibr cost adapters
try:
    from kalibr.cost_adapter import CostAdapterFactory
except ImportError:
    CostAdapterFactory = None

# Import tiktoken for token counting
try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


def _count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens for given text."""
    if not text:
        return 0

    if HAS_TIKTOKEN:
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            pass

    return len(str(text)) // 4


def _get_provider_from_model(model: str) -> str:
    """Infer provider from model name."""
    if not model:
        return "openai"
    model_lower = model.lower()

    if any(x in model_lower for x in ["gpt", "text-davinci", "o1", "o3"]):
        return "openai"
    elif any(x in model_lower for x in ["claude"]):
        return "anthropic"
    elif any(x in model_lower for x in ["gemini", "palm"]):
        return "google"
    else:
        return "openai"


class EventBatcher:
    """Shared event batching for callbacks."""

    _instances: Dict[str, "EventBatcher"] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        batch_size: int = 100,
        flush_interval: float = 2.0,
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._event_queue: queue.Queue = queue.Queue(maxsize=5000)
        self._client = httpx.Client(timeout=10.0)
        self._shutdown = False

        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        atexit.register(self.shutdown)

    @classmethod
    def get_instance(
        cls,
        endpoint: str,
        api_key: str,
        batch_size: int = 100,
        flush_interval: float = 2.0,
    ) -> "EventBatcher":
        """Get or create a shared EventBatcher instance."""
        key = f"{endpoint}:{api_key}"
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = cls(
                    endpoint=endpoint,
                    api_key=api_key,
                    batch_size=batch_size,
                    flush_interval=flush_interval,
                )
            return cls._instances[key]

    def enqueue(self, event: Dict[str, Any]):
        """Add event to queue."""
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except:
                pass

    def _flush_loop(self):
        """Background thread to flush events."""
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

        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        """Send batch to backend."""
        if not batch:
            return

        try:
            payload = {"events": batch}
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            self._client.post(self.endpoint, json=payload, headers=headers)
        except Exception:
            pass

    def shutdown(self):
        """Shutdown batcher."""
        if self._shutdown:
            return
        self._shutdown = True
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)
        self._client.close()

    def flush(self):
        """Force flush pending events."""
        events = []
        while True:
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except queue.Empty:
                break
        if events:
            self._send_batch(events)


class KalibrAgentCallback:
    """Callback for CrewAI Agent step_callback.

    This callback is invoked after each step in an agent's execution,
    capturing tool calls, agent actions, and intermediate results.

    Args:
        api_key: Kalibr API key
        endpoint: Backend endpoint URL
        tenant_id: Tenant identifier
        environment: Environment (prod/staging/dev)
        service: Service name
        workflow_id: Workflow identifier
        metadata: Additional metadata for all events

    Usage:
        from kalibr_crewai import KalibrAgentCallback
        from crewai import Agent

        callback = KalibrAgentCallback(tenant_id="my-tenant")

        agent = Agent(
            role="Researcher",
            goal="Find information",
            step_callback=callback,
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None,
        environment: Optional[str] = None,
        service: Optional[str] = None,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.api_key = api_key or os.getenv("KALIBR_API_KEY", "")
        self.endpoint = endpoint or os.getenv(
            "KALIBR_ENDPOINT",
            os.getenv("KALIBR_API_ENDPOINT", "http://localhost:8001/api/v1/traces")
        )
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "default")
        self.environment = environment or os.getenv("KALIBR_ENVIRONMENT", "prod")
        self.service = service or os.getenv("KALIBR_SERVICE", "crewai-app")
        self.workflow_id = workflow_id or os.getenv("KALIBR_WORKFLOW_ID", "default-workflow")
        self.default_metadata = metadata or {}

        # Get shared batcher
        self._batcher = EventBatcher.get_instance(
            endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # Trace context
        self._trace_id: Optional[str] = None
        self._agent_span_id: Optional[str] = None
        self._step_count: int = 0

    def __call__(self, step_output: Any) -> None:
        """Called after each agent step.

        Args:
            step_output: The output from the agent step. Can be:
                - AgentAction (tool call)
                - AgentFinish (final answer)
                - Other step output types
        """
        try:
            self._handle_step(step_output)
        except Exception as e:
            # Don't let callback errors break the agent
            pass

    def _handle_step(self, step_output: Any):
        """Process step output and create trace event."""
        now = datetime.now(timezone.utc)
        self._step_count += 1

        # Initialize trace on first step
        if not self._trace_id:
            self._trace_id = str(uuid.uuid4())
            self._agent_span_id = str(uuid.uuid4())

        span_id = str(uuid.uuid4())

        # Extract step information
        step_type = "agent_step"
        operation = "agent_step"
        tool_name = None
        tool_input = None
        output_text = ""
        status = "success"

        # Handle different step output types
        if hasattr(step_output, "tool"):
            # AgentAction - tool call
            step_type = "tool_call"
            tool_name = step_output.tool
            operation = f"tool:{tool_name}"
            if hasattr(step_output, "tool_input"):
                tool_input = str(step_output.tool_input)

        elif hasattr(step_output, "return_values"):
            # AgentFinish - final output
            step_type = "agent_finish"
            operation = "agent_finish"
            output_text = str(step_output.return_values)

        elif hasattr(step_output, "output"):
            # Generic step with output
            output_text = str(step_output.output)

        elif hasattr(step_output, "log"):
            # Step with log
            output_text = str(step_output.log)

        else:
            # Fallback
            output_text = str(step_output)

        # Count tokens
        input_tokens = _count_tokens(tool_input or "", "gpt-4")
        output_tokens = _count_tokens(output_text, "gpt-4")

        # Build event
        event = {
            "schema_version": "1.0",
            "trace_id": self._trace_id,
            "span_id": span_id,
            "parent_span_id": self._agent_span_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "provider": "crewai",
            "model_id": "agent",
            "model_name": "crewai-agent",
            "operation": operation,
            "endpoint": operation,
            "duration_ms": 0,  # Step timing not available
            "latency_ms": 0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": 0.0,  # Cost tracked at LLM level
            "total_cost_usd": 0.0,
            "status": status,
            "timestamp": now.isoformat(),
            "ts_start": now.isoformat(),
            "ts_end": now.isoformat(),
            "environment": self.environment,
            "service": self.service,
            "runtime_env": os.getenv("RUNTIME_ENV", "local"),
            "sandbox_id": os.getenv("SANDBOX_ID", "local"),
            "metadata": {
                **self.default_metadata,
                "span_type": step_type,
                "crewai": True,
                "step_number": self._step_count,
                "tool_name": tool_name,
                "tool_input": tool_input[:500] if tool_input else None,
                "output_preview": output_text[:500] if output_text else None,
            },
        }

        self._batcher.enqueue(event)

    def reset(self):
        """Reset trace context for new agent run."""
        self._trace_id = None
        self._agent_span_id = None
        self._step_count = 0

    def flush(self):
        """Force flush pending events."""
        self._batcher.flush()


class KalibrTaskCallback:
    """Callback for CrewAI Task callback.

    This callback is invoked when a task completes, capturing the
    full task execution including description, output, and metrics.

    Args:
        api_key: Kalibr API key
        endpoint: Backend endpoint URL
        tenant_id: Tenant identifier
        environment: Environment (prod/staging/dev)
        service: Service name
        workflow_id: Workflow identifier
        metadata: Additional metadata for all events

    Usage:
        from kalibr_crewai import KalibrTaskCallback
        from crewai import Task

        callback = KalibrTaskCallback(tenant_id="my-tenant")

        task = Task(
            description="Research AI trends",
            agent=my_agent,
            callback=callback,
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None,
        environment: Optional[str] = None,
        service: Optional[str] = None,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.api_key = api_key or os.getenv("KALIBR_API_KEY", "")
        self.endpoint = endpoint or os.getenv(
            "KALIBR_ENDPOINT",
            os.getenv("KALIBR_API_ENDPOINT", "http://localhost:8001/api/v1/traces")
        )
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "default")
        self.environment = environment or os.getenv("KALIBR_ENVIRONMENT", "prod")
        self.service = service or os.getenv("KALIBR_SERVICE", "crewai-app")
        self.workflow_id = workflow_id or os.getenv("KALIBR_WORKFLOW_ID", "default-workflow")
        self.default_metadata = metadata or {}

        # Get shared batcher
        self._batcher = EventBatcher.get_instance(
            endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # Trace context
        self._trace_id: Optional[str] = None
        self._crew_span_id: Optional[str] = None

    def __call__(self, task_output: Any) -> None:
        """Called when task completes.

        Args:
            task_output: TaskOutput object with:
                - description: Task description
                - raw: Raw output string
                - pydantic: Optional Pydantic model output
                - json_dict: Optional JSON dict output
                - agent: Agent role that executed the task
                - output_format: Output format type
        """
        try:
            self._handle_task_complete(task_output)
        except Exception as e:
            # Don't let callback errors break the task
            pass

    def _handle_task_complete(self, task_output: Any):
        """Process task output and create trace event."""
        now = datetime.now(timezone.utc)

        # Initialize trace if needed
        if not self._trace_id:
            self._trace_id = str(uuid.uuid4())

        span_id = str(uuid.uuid4())

        # Extract task information
        description = ""
        raw_output = ""
        agent_role = "unknown"

        if hasattr(task_output, "description"):
            description = str(task_output.description)

        if hasattr(task_output, "raw"):
            raw_output = str(task_output.raw)
        elif hasattr(task_output, "output"):
            raw_output = str(task_output.output)
        else:
            raw_output = str(task_output)

        if hasattr(task_output, "agent"):
            agent_role = str(task_output.agent)

        # Token counting
        input_tokens = _count_tokens(description, "gpt-4")
        output_tokens = _count_tokens(raw_output, "gpt-4")

        # Build operation name from description
        operation = "task_complete"
        if description:
            # Create short operation name from description
            words = description.split()[:5]
            operation = f"task:{' '.join(words)}"[:64]

        # Build event
        event = {
            "schema_version": "1.0",
            "trace_id": self._trace_id,
            "span_id": span_id,
            "parent_span_id": self._crew_span_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "provider": "crewai",
            "model_id": "task",
            "model_name": agent_role,
            "operation": operation,
            "endpoint": "task_complete",
            "duration_ms": 0,  # Task timing not available in callback
            "latency_ms": 0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": 0.0,  # Cost tracked at LLM level
            "total_cost_usd": 0.0,
            "status": "success",
            "timestamp": now.isoformat(),
            "ts_start": now.isoformat(),
            "ts_end": now.isoformat(),
            "environment": self.environment,
            "service": self.service,
            "runtime_env": os.getenv("RUNTIME_ENV", "local"),
            "sandbox_id": os.getenv("SANDBOX_ID", "local"),
            "metadata": {
                **self.default_metadata,
                "span_type": "task",
                "crewai": True,
                "task_description": description[:500] if description else None,
                "agent_role": agent_role,
                "output_preview": raw_output[:500] if raw_output else None,
                "output_format": getattr(task_output, "output_format", None),
            },
        }

        self._batcher.enqueue(event)

    def set_trace_context(self, trace_id: str, crew_span_id: Optional[str] = None):
        """Set trace context for linking tasks to a crew execution.

        Args:
            trace_id: Parent trace ID
            crew_span_id: Parent crew span ID
        """
        self._trace_id = trace_id
        self._crew_span_id = crew_span_id

    def reset(self):
        """Reset trace context for new crew run."""
        self._trace_id = None
        self._crew_span_id = None

    def flush(self):
        """Force flush pending events."""
        self._batcher.flush()
