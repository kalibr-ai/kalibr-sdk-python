"""Decorator functions for automatic tracing.

Provides clean decorator-based API for tracing LLM calls:

@trace(operation="chat_completion", vendor="openai", model="gpt-4")
def my_llm_call(prompt):
    return client.chat.completions.create(...)
"""

from functools import wraps
from typing import Any, Callable, Optional

from .tokens import count_tokens
from .tracer import Tracer


def create_trace_decorator(tracer: Tracer):
    """Create a trace decorator bound to a tracer instance.

    Args:
        tracer: Tracer instance

    Returns:
        Trace decorator function
    """

    def trace(
        operation: str = "model_call",
        vendor: str = "unknown",
        model: str = "unknown",
        endpoint: Optional[str] = None,
        extract_tokens: bool = True,
    ):
        """Decorator to trace function calls.

        Args:
            operation: Operation type (chat_completion, embedding, etc.)
            vendor: Vendor name (openai, anthropic, etc.)
            model: Model identifier
            endpoint: API endpoint or function name
            extract_tokens: Whether to extract token counts from args/result

        Example:
            @trace(operation="chat_completion", vendor="openai", model="gpt-4")
            def call_openai(prompt):
                return openai.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Create span context
                with tracer.create_span(
                    operation=operation,
                    vendor=vendor,
                    model_name=model,
                    endpoint=endpoint or func.__name__,
                ) as span:
                    try:
                        # Execute function
                        result = func(*args, **kwargs)

                        # Extract tokens if enabled
                        if extract_tokens:
                            tokens_in, tokens_out = _extract_tokens(args, kwargs, result, model)
                            span.set_tokens(tokens_in, tokens_out)

                        return result

                    except Exception as e:
                        # Capture error
                        span.set_error(e)
                        raise

            return wrapper

        return decorator

    return trace


def _extract_tokens(args, kwargs, result, model: str) -> tuple[int, int]:
    """Extract token counts from function args and result.

    Args:
        args: Function positional arguments
        kwargs: Function keyword arguments
        result: Function return value
        model: Model identifier

    Returns:
        Tuple of (tokens_in, tokens_out)
    """
    tokens_in = 0
    tokens_out = 0

    # Try to extract prompt from common arg patterns
    prompt = None
    response_text = None

    # Extract from OpenAI-style calls
    if "messages" in kwargs:
        messages = kwargs["messages"]
        if isinstance(messages, list):
            prompt = "\n".join([str(m.get("content", "")) for m in messages])
    elif "prompt" in kwargs:
        prompt = kwargs["prompt"]
    elif args and isinstance(args[0], str):
        prompt = args[0]

    # Extract response
    if hasattr(result, "choices") and result.choices:  # OpenAI response
        choice = result.choices[0]
        if hasattr(choice, "message") and hasattr(choice.message, "content"):
            response_text = choice.message.content
    elif hasattr(result, "content"):  # Anthropic response
        if isinstance(result.content, list):
            response_text = "\n".join(
                [block.text for block in result.content if hasattr(block, "text")]
            )
        else:
            response_text = str(result.content)
    elif isinstance(result, dict):
        if "content" in result:
            response_text = result["content"]
        elif "text" in result:
            response_text = result["text"]
    elif isinstance(result, str):
        response_text = result

    # Count tokens
    if prompt:
        tokens_in = count_tokens(prompt, model)
    if response_text:
        tokens_out = count_tokens(response_text, model)

    return tokens_in, tokens_out
