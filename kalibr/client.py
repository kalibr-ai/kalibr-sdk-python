"""Kalibr client with context propagation and batch flushing.

Refactored for Phase 1 - SDK Stabilization:
- Uses modular tracer and cost adapters
- Supports new event schema v1.0
- Enhanced error handling with stack traces
- Environment-based configuration
"""

import atexit
import hashlib
import hmac
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

import httpx

from .decorators import create_trace_decorator
from .tracer import Tracer
from .utils import (
    load_config_from_env,
    log_error,
    log_info,
    log_success,
    log_warning,
    serialize_event,
    validate_event,
)


class KalibrClient:
    """Kalibr observability client with Phase 1 enhancements.

    Features:
    - Modular tracer with cost adapters
    - New event schema v1.0
    - Enhanced error handling
    - Environment-based configuration

    Args:
        api_key: Kalibr API key
        endpoint: Collector endpoint URL (optional, can load from env)
        tenant_id: Tenant identifier (optional, can load from env)
        environment: Environment (prod/staging/dev, can load from env)
        service: Service name (optional, can load from env)
        secret: HMAC secret for request signing
        batch_size: Max events per batch
        flush_interval: Flush interval in seconds
        max_queue_size: Max queue size (drops oldest on overflow)
    """

    def __init__(
        self,
        api_key: str = None,
        endpoint: str = None,
        tenant_id: str = None,
        environment: str = None,
        service: str = None,
        workflow_id: str = None,
        workflow_version: str = None,
        secret: Optional[str] = None,
        batch_size: int = 100,
        flush_interval: float = 2.0,
        max_queue_size: int = 5000,
    ):
        # Load config from environment if not provided
        env_config = load_config_from_env()

        self.api_key = api_key or env_config.get("auth_token", "")
        self.endpoint = endpoint or env_config.get(
            "api_endpoint", "https://api.kalibr.systems/api/v1/traces"
        )
        self.tenant_id = tenant_id or env_config.get("tenant_id", "default")
        self.environment = environment or env_config.get("environment", "prod")
        self.service = service or env_config.get("project_name", "kalibr-app")
        self.secret = secret

        # Workflow configuration (can override env)
        if workflow_id:
            env_config["workflow_id"] = workflow_id
        if workflow_version:
            env_config["workflow_version"] = workflow_version
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Extract workflow and runtime fields from config
        self.workflow_id = env_config.get("workflow_id", "default-workflow")
        self.workflow_version = env_config.get("workflow_version", "1.0")
        self.sandbox_id = env_config.get("sandbox_id", "local")
        self.runtime_env = env_config.get("runtime_env", "local")
        self.parent_trace_id = env_config.get("parent_trace_id")

        # Create tracer instance
        self.tracer = Tracer(
            tenant_id=self.tenant_id,
            environment=self.environment,
            service=self.service,
            workflow_id=self.workflow_id,
            workflow_version=self.workflow_version,
            sandbox_id=self.sandbox_id,
            runtime_env=self.runtime_env,
            parent_trace_id=self.parent_trace_id,
        )

        # Event queue
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.max_queue_size = max_queue_size

        # HTTP client
        self.client = httpx.Client(timeout=10.0)

        # Background flusher thread
        self._shutdown = False
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        # Register cleanup
        atexit.register(self.shutdown)

        log_success(
            f"Kalibr client initialized: {self.tenant_id} @ {self.environment} (service: {self.service})"
        )

    def _flush_loop(self):
        """Background thread to flush events periodically."""
        batch = []
        last_flush = time.time()

        while not self._shutdown:
            try:
                # Get event with timeout
                try:
                    event = self.queue.get(timeout=0.1)
                    batch.append(event)
                except queue.Empty:
                    pass

                # Flush if batch is full or interval elapsed
                now = time.time()
                should_flush = len(batch) >= self.batch_size or (
                    batch and now - last_flush >= self.flush_interval
                )

                if should_flush:
                    self._send_batch(batch)
                    batch = []
                    last_flush = now

            except Exception as e:
                log_warning(f"Flush loop error: {e}")

        # Final flush on shutdown
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: list):
        """Send batch to collector with validation."""
        if not batch:
            return

        try:
            # Validate events
            valid_events = []
            for event in batch:
                if validate_event(event):
                    valid_events.append(event)
                else:
                    log_warning(f"Invalid event skipped: {event.get('span_id', 'unknown')}")

            if not valid_events:
                log_warning("No valid events in batch")
                return

            # ✅ Fixed Bug 2: Send as JSON dict instead of NDJSON string
            # Backend expects: {"events": [event_dict]}
            payload = {"events": valid_events}

            # Create HMAC signature if secret provided
            headers = {"X-API-Key": self.api_key} if self.api_key else {}
            if self.secret:
                # Sign the JSON payload
                body = serialize_event(payload).encode("utf-8")
                signature = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
                headers["X-Signature"] = signature

            # Send request with json parameter (automatically serializes dict)
            response = self.client.post(
                self.endpoint,
                json=payload,  # ✅ Sends as JSON object, not string
                headers=headers,
            )
            response.raise_for_status()

            result = response.json()
            accepted = result.get("accepted", 0)
            rejected = result.get("rejected", 0)

            if rejected > 0:
                log_warning(f"Batch: {accepted} accepted, {rejected} rejected")

        except Exception as e:
            log_error(f"Batch send failed: {e}")

    def _enqueue(self, event: Dict):
        """Add event to queue (drop oldest if full)."""
        try:
            self.queue.put_nowait(event)
        except queue.Full:
            # Drop oldest event
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(event)
            except:
                pass

    def shutdown(self):
        """Shutdown client and flush remaining events."""
        if self._shutdown:
            return

        log_info("Shutting down Kalibr client...")
        self._shutdown = True

        # Wait for flush thread
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)

        # Close HTTP client
        self.client.close()
        log_success("Kalibr client shutdown complete")

    def trace(
        self,
        operation: str = "model_call",
        vendor: str = "unknown",
        model: str = "unknown",
        endpoint: Optional[str] = None,
    ):
        """Decorator to trace function calls using new Phase 1 tracer.

        Args:
            operation: Operation type (chat_completion, embedding, etc.)
            vendor: Vendor name (openai, anthropic, etc.)
            model: Model identifier (gpt-4, claude-3-sonnet, etc.)
            endpoint: API endpoint or function name

        Example:
            @kalibr.trace(operation="chat_completion", vendor="openai", model="gpt-4")
            def call_openai(prompt):
                return openai.chat.completions.create(...)
        """
        # Create decorator using the new tracer system
        trace_decorator = create_trace_decorator(self.tracer)
        decorator_func = trace_decorator(
            operation=operation, vendor=vendor, model=model, endpoint=endpoint
        )

        # Wrap to enqueue events from tracer
        def enhanced_decorator(func: Callable) -> Callable:
            wrapped = decorator_func(func)

            def wrapper(*args, **kwargs):
                from .context import trace_context

                # Clear events before call
                ctx = trace_context.get()
                ctx["events"] = []
                trace_context.set(ctx)

                try:
                    result = wrapped(*args, **kwargs)

                    # Enqueue events created by tracer
                    ctx = trace_context.get()
                    events = ctx.get("events", [])
                    for event in events:
                        self._enqueue(event)

                    return result

                except Exception as e:
                    # Enqueue error events too
                    ctx = trace_context.get()
                    events = ctx.get("events", [])
                    for event in events:
                        self._enqueue(event)
                    raise

            return wrapper

        return enhanced_decorator
