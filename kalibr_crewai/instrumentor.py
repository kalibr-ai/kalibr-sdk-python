"""Kalibr Auto-Instrumentation for CrewAI.

This module provides automatic instrumentation for CrewAI applications
by wrapping key methods to capture telemetry.
"""

import os
import time
import traceback
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from .callbacks import EventBatcher, _count_tokens, _get_provider_from_model

# Import Kalibr cost adapters
try:
    from kalibr.cost_adapter import CostAdapterFactory
except ImportError:
    CostAdapterFactory = None


def _extract_model_from_agent(agent) -> tuple[str, str]:
    """Extract model name and provider from agent's LLM config.

    Args:
        agent: CrewAI agent instance

    Returns:
        Tuple of (model_name, provider)
    """
    model_name = "unknown"
    provider = "openai"

    if not hasattr(agent, "llm"):
        return model_name, provider

    llm = agent.llm

    # Case 1: LLM is a string like "openai/gpt-4o-mini" or "gpt-4"
    if isinstance(llm, str):
        if "/" in llm:
            parts = llm.split("/", 1)
            provider = parts[0]
            model_name = parts[1]
        else:
            model_name = llm
            provider = _get_provider_from_model(llm)
        return model_name, provider

    # Case 2: LLM has model or model_name attribute
    if hasattr(llm, "model"):
        model_name = str(llm.model)
    elif hasattr(llm, "model_name"):
        model_name = str(llm.model_name)

    # Parse provider from model string if it contains "/"
    if "/" in model_name:
        parts = model_name.split("/", 1)
        provider = parts[0]
        model_name = parts[1]
    else:
        provider = _get_provider_from_model(model_name)

    return model_name, provider


def _calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost using CostAdapterFactory.

    Args:
        provider: Provider name (openai, anthropic, etc.)
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    if CostAdapterFactory is None:
        return 0.0

    try:
        return CostAdapterFactory.compute_cost(provider, model, input_tokens, output_tokens)
    except Exception:
        return 0.0


class KalibrCrewAIInstrumentor:
    """Auto-instrumentation for CrewAI.

    This instrumentor wraps CrewAI's Crew, Agent, and Task classes to
    automatically capture telemetry without requiring manual callbacks.

    Args:
        api_key: Kalibr API key
        endpoint: Backend endpoint URL
        tenant_id: Tenant identifier
        environment: Environment (prod/staging/dev)
        service: Service name
        workflow_id: Workflow identifier
        capture_input: Whether to capture inputs (default: True)
        capture_output: Whether to capture outputs (default: True)

    Usage:
        from kalibr_crewai import KalibrCrewAIInstrumentor

        # Instrument before creating crews
        instrumentor = KalibrCrewAIInstrumentor(tenant_id="my-tenant")
        instrumentor.instrument()

        # Use CrewAI normally - all operations are traced
        crew = Crew(agents=[...], tasks=[...])
        result = crew.kickoff()

        # Optionally uninstrument
        instrumentor.uninstrument()
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
    ):
        self.api_key = api_key or os.getenv("KALIBR_API_KEY", "")
        self.endpoint = endpoint or os.getenv(
            "KALIBR_ENDPOINT",
            os.getenv("KALIBR_API_ENDPOINT", "https://api.kalibr.systems/api/v1/traces")
        )
        self.tenant_id = tenant_id or os.getenv("KALIBR_TENANT_ID", "default")
        self.environment = environment or os.getenv("KALIBR_ENVIRONMENT", "prod")
        self.service = service or os.getenv("KALIBR_SERVICE", "crewai-app")
        self.workflow_id = workflow_id or os.getenv("KALIBR_WORKFLOW_ID", "default-workflow")
        self.capture_input = capture_input
        self.capture_output = capture_output

        # Batcher for sending events
        self._batcher: Optional[EventBatcher] = None

        # Original methods to restore on uninstrument
        self._originals: Dict[str, Any] = {}

        # Instrumentation state
        self._is_instrumented = False

        # Accumulated metrics for crew-level aggregation
        self._accumulated_tokens = {"input": 0, "output": 0}
        self._accumulated_cost = 0.0

    def instrument(self) -> bool:
        """Instrument CrewAI classes.

        Returns:
            True if instrumentation was successful
        """
        if self._is_instrumented:
            return True

        try:
            from crewai import Crew, Agent, Task
        except ImportError:
            print("[Kalibr] CrewAI not installed, skipping instrumentation")
            return False

        # Initialize batcher
        self._batcher = EventBatcher.get_instance(
            endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # Instrument Crew.kickoff
        self._originals["Crew.kickoff"] = Crew.kickoff
        Crew.kickoff = self._wrap_crew_kickoff(Crew.kickoff)

        # Instrument Crew.kickoff_async if available
        if hasattr(Crew, "kickoff_async"):
            self._originals["Crew.kickoff_async"] = Crew.kickoff_async
            Crew.kickoff_async = self._wrap_crew_kickoff_async(Crew.kickoff_async)

        # Instrument Agent.execute_task
        if hasattr(Agent, "execute_task"):
            self._originals["Agent.execute_task"] = Agent.execute_task
            Agent.execute_task = self._wrap_agent_execute(Agent.execute_task)

        # Instrument Task.execute_sync if available
        if hasattr(Task, "execute_sync"):
            self._originals["Task.execute_sync"] = Task.execute_sync
            Task.execute_sync = self._wrap_task_execute(Task.execute_sync)

        self._is_instrumented = True
        return True

    def uninstrument(self) -> bool:
        """Remove instrumentation and restore original methods.

        Returns:
            True if uninstrumentation was successful
        """
        if not self._is_instrumented:
            return True

        try:
            from crewai import Crew, Agent, Task

            # Restore original methods
            if "Crew.kickoff" in self._originals:
                Crew.kickoff = self._originals["Crew.kickoff"]

            if "Crew.kickoff_async" in self._originals:
                Crew.kickoff_async = self._originals["Crew.kickoff_async"]

            if "Agent.execute_task" in self._originals:
                Agent.execute_task = self._originals["Agent.execute_task"]

            if "Task.execute_sync" in self._originals:
                Task.execute_sync = self._originals["Task.execute_sync"]

            self._originals.clear()
            self._is_instrumented = False
            return True

        except ImportError:
            return False

    def _wrap_crew_kickoff(self, original_method: Callable) -> Callable:
        """Wrap Crew.kickoff to capture crew execution."""
        instrumentor = self

        @wraps(original_method)
        def wrapper(crew_self, *args, **kwargs):
            trace_id = str(uuid.uuid4())
            span_id = str(uuid.uuid4())
            start_time = time.time()
            ts_start = datetime.now(timezone.utc)

            # Reset accumulators before crew execution
            instrumentor._accumulated_tokens = {"input": 0, "output": 0}
            instrumentor._accumulated_cost = 0.0

            # Capture crew info
            crew_name = getattr(crew_self, "name", None) or "unnamed_crew"
            agents = getattr(crew_self, "agents", [])
            agent_count = len(agents)
            task_count = len(getattr(crew_self, "tasks", []))

            # Extract model from first agent if available
            model_name = "unknown"
            provider = "crewai"
            if agents:
                model_name, provider = _extract_model_from_agent(agents[0])

            status = "success"
            error_type = None
            error_message = None
            result = None

            try:
                result = original_method(crew_self, *args, **kwargs)
                return result

            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                error_message = str(e)[:512]
                raise

            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                ts_end = datetime.now(timezone.utc)

                # Build output info
                output_preview = None
                if instrumentor.capture_output and result is not None:
                    output_preview = str(result)[:500]

                # Get accumulated metrics from child agent/task executions
                input_tokens = instrumentor._accumulated_tokens["input"]
                output_tokens = instrumentor._accumulated_tokens["output"]
                total_tokens = input_tokens + output_tokens
                cost_usd = instrumentor._accumulated_cost

                # Create event with aggregated metrics
                event = {
                    "schema_version": "1.0",
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": None,
                    "tenant_id": instrumentor.tenant_id,
                    "workflow_id": instrumentor.workflow_id,
                    "provider": provider,
                    "model_id": model_name,
                    "model_name": model_name,
                    "operation": f"crew:{crew_name}",
                    "endpoint": "crew.kickoff",
                    "duration_ms": duration_ms,
                    "latency_ms": duration_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                    "total_cost_usd": cost_usd,
                    "status": status,
                    "error_type": error_type,
                    "error_message": error_message,
                    "timestamp": ts_start.isoformat(),
                    "ts_start": ts_start.isoformat(),
                    "ts_end": ts_end.isoformat(),
                    "environment": instrumentor.environment,
                    "service": instrumentor.service,
                    "runtime_env": os.getenv("RUNTIME_ENV", "local"),
                    "sandbox_id": os.getenv("SANDBOX_ID", "local"),
                    "metadata": {
                        "span_type": "crew",
                        "crewai": True,
                        "crew_name": crew_name,
                        "agent_count": agent_count,
                        "task_count": task_count,
                        "output_preview": output_preview,
                    },
                }

                if instrumentor._batcher:
                    instrumentor._batcher.enqueue(event)

        return wrapper

    def _wrap_crew_kickoff_async(self, original_method: Callable) -> Callable:
        """Wrap Crew.kickoff_async to capture async crew execution."""
        instrumentor = self

        @wraps(original_method)
        async def wrapper(crew_self, *args, **kwargs):
            trace_id = str(uuid.uuid4())
            span_id = str(uuid.uuid4())
            start_time = time.time()
            ts_start = datetime.now(timezone.utc)

            # Reset accumulators before crew execution
            instrumentor._accumulated_tokens = {"input": 0, "output": 0}
            instrumentor._accumulated_cost = 0.0

            crew_name = getattr(crew_self, "name", None) or "unnamed_crew"
            agents = getattr(crew_self, "agents", [])
            agent_count = len(agents)
            task_count = len(getattr(crew_self, "tasks", []))

            # Extract model from first agent if available
            model_name = "unknown"
            provider = "crewai"
            if agents:
                model_name, provider = _extract_model_from_agent(agents[0])

            status = "success"
            error_type = None
            error_message = None
            result = None

            try:
                result = await original_method(crew_self, *args, **kwargs)
                return result

            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                error_message = str(e)[:512]
                raise

            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                ts_end = datetime.now(timezone.utc)

                output_preview = None
                if instrumentor.capture_output and result is not None:
                    output_preview = str(result)[:500]

                # Get accumulated metrics from child agent/task executions
                input_tokens = instrumentor._accumulated_tokens["input"]
                output_tokens = instrumentor._accumulated_tokens["output"]
                total_tokens = input_tokens + output_tokens
                cost_usd = instrumentor._accumulated_cost

                # Create event with aggregated metrics
                event = {
                    "schema_version": "1.0",
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": None,
                    "tenant_id": instrumentor.tenant_id,
                    "workflow_id": instrumentor.workflow_id,
                    "provider": provider,
                    "model_id": model_name,
                    "model_name": model_name,
                    "operation": f"crew:{crew_name}",
                    "endpoint": "crew.kickoff_async",
                    "duration_ms": duration_ms,
                    "latency_ms": duration_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                    "total_cost_usd": cost_usd,
                    "status": status,
                    "error_type": error_type,
                    "error_message": error_message,
                    "timestamp": ts_start.isoformat(),
                    "ts_start": ts_start.isoformat(),
                    "ts_end": ts_end.isoformat(),
                    "environment": instrumentor.environment,
                    "service": instrumentor.service,
                    "runtime_env": os.getenv("RUNTIME_ENV", "local"),
                    "sandbox_id": os.getenv("SANDBOX_ID", "local"),
                    "metadata": {
                        "span_type": "crew",
                        "crewai": True,
                        "async": True,
                        "crew_name": crew_name,
                        "agent_count": agent_count,
                        "task_count": task_count,
                        "output_preview": output_preview,
                    },
                }

                if instrumentor._batcher:
                    instrumentor._batcher.enqueue(event)

        return wrapper

    def _wrap_agent_execute(self, original_method: Callable) -> Callable:
        """Wrap Agent.execute_task to capture agent execution."""
        instrumentor = self

        @wraps(original_method)
        def wrapper(agent_self, task, *args, **kwargs):
            span_id = str(uuid.uuid4())
            start_time = time.time()
            ts_start = datetime.now(timezone.utc)

            # Get agent info
            role = getattr(agent_self, "role", "unknown")
            goal = getattr(agent_self, "goal", "")

            # Extract model from agent's LLM config
            model_name, provider = _extract_model_from_agent(agent_self)

            # Get task info
            task_description = ""
            if hasattr(task, "description"):
                task_description = str(task.description)

            status = "success"
            error_type = None
            error_message = None
            result = None

            try:
                result = original_method(agent_self, task, *args, **kwargs)
                return result

            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                error_message = str(e)[:512]
                raise

            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                ts_end = datetime.now(timezone.utc)

                output_preview = None
                if instrumentor.capture_output and result is not None:
                    output_preview = str(result)[:500]

                # Token estimation
                input_tokens = _count_tokens(task_description + goal, model_name)
                output_tokens = _count_tokens(output_preview or "", model_name)

                # Calculate cost using CostAdapterFactory
                cost_usd = _calculate_cost(provider, model_name, input_tokens, output_tokens)

                # Accumulate metrics for crew-level aggregation
                instrumentor._accumulated_tokens["input"] += input_tokens
                instrumentor._accumulated_tokens["output"] += output_tokens
                instrumentor._accumulated_cost += cost_usd

                event = {
                    "schema_version": "1.0",
                    "trace_id": str(uuid.uuid4()),  # TODO: Link to crew trace
                    "span_id": span_id,
                    "parent_span_id": None,
                    "tenant_id": instrumentor.tenant_id,
                    "workflow_id": instrumentor.workflow_id,
                    "provider": provider,
                    "model_id": model_name,
                    "model_name": model_name,
                    "operation": f"agent:{role}",
                    "endpoint": "agent.execute_task",
                    "duration_ms": duration_ms,
                    "latency_ms": duration_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "cost_usd": cost_usd,
                    "total_cost_usd": cost_usd,
                    "status": status,
                    "error_type": error_type,
                    "error_message": error_message,
                    "timestamp": ts_start.isoformat(),
                    "ts_start": ts_start.isoformat(),
                    "ts_end": ts_end.isoformat(),
                    "environment": instrumentor.environment,
                    "service": instrumentor.service,
                    "runtime_env": os.getenv("RUNTIME_ENV", "local"),
                    "sandbox_id": os.getenv("SANDBOX_ID", "local"),
                    "metadata": {
                        "span_type": "agent",
                        "crewai": True,
                        "agent_role": role,
                        "agent_goal": goal[:200] if goal else None,
                        "task_description": task_description[:200] if task_description else None,
                        "output_preview": output_preview,
                    },
                }

                if instrumentor._batcher:
                    instrumentor._batcher.enqueue(event)

        return wrapper

    def _wrap_task_execute(self, original_method: Callable) -> Callable:
        """Wrap Task.execute_sync to capture task execution."""
        instrumentor = self

        @wraps(original_method)
        def wrapper(task_self, *args, **kwargs):
            span_id = str(uuid.uuid4())
            start_time = time.time()
            ts_start = datetime.now(timezone.utc)

            description = getattr(task_self, "description", "")
            expected_output = getattr(task_self, "expected_output", "")

            # Try to extract model from task's agent
            model_name = "unknown"
            provider = "openai"
            agent = getattr(task_self, "agent", None)
            if agent:
                model_name, provider = _extract_model_from_agent(agent)

            status = "success"
            error_type = None
            error_message = None
            result = None

            try:
                result = original_method(task_self, *args, **kwargs)
                return result

            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                error_message = str(e)[:512]
                raise

            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                ts_end = datetime.now(timezone.utc)

                output_preview = None
                if instrumentor.capture_output and result is not None:
                    if hasattr(result, "raw"):
                        output_preview = str(result.raw)[:500]
                    else:
                        output_preview = str(result)[:500]

                input_tokens = _count_tokens(description, model_name)
                output_tokens = _count_tokens(output_preview or "", model_name)

                # Calculate cost using CostAdapterFactory
                cost_usd = _calculate_cost(provider, model_name, input_tokens, output_tokens)

                # Accumulate metrics for crew-level aggregation
                instrumentor._accumulated_tokens["input"] += input_tokens
                instrumentor._accumulated_tokens["output"] += output_tokens
                instrumentor._accumulated_cost += cost_usd

                event = {
                    "schema_version": "1.0",
                    "trace_id": str(uuid.uuid4()),
                    "span_id": span_id,
                    "parent_span_id": None,
                    "tenant_id": instrumentor.tenant_id,
                    "workflow_id": instrumentor.workflow_id,
                    "provider": provider,
                    "model_id": model_name,
                    "model_name": model_name,
                    "operation": f"task:{description[:30]}..." if len(description) > 30 else f"task:{description}",
                    "endpoint": "task.execute_sync",
                    "duration_ms": duration_ms,
                    "latency_ms": duration_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "cost_usd": cost_usd,
                    "total_cost_usd": cost_usd,
                    "status": status,
                    "error_type": error_type,
                    "error_message": error_message,
                    "timestamp": ts_start.isoformat(),
                    "ts_start": ts_start.isoformat(),
                    "ts_end": ts_end.isoformat(),
                    "environment": instrumentor.environment,
                    "service": instrumentor.service,
                    "runtime_env": os.getenv("RUNTIME_ENV", "local"),
                    "sandbox_id": os.getenv("SANDBOX_ID", "local"),
                    "metadata": {
                        "span_type": "task",
                        "crewai": True,
                        "task_description": description[:200] if description else None,
                        "expected_output": expected_output[:200] if expected_output else None,
                        "output_preview": output_preview,
                    },
                }

                if instrumentor._batcher:
                    instrumentor._batcher.enqueue(event)

        return wrapper

    def flush(self):
        """Force flush pending events."""
        if self._batcher:
            self._batcher.flush()

    @property
    def is_instrumented(self) -> bool:
        """Check if CrewAI is currently instrumented."""
        return self._is_instrumented
