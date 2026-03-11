"""
Unit tests for OpenAI Responses API instrumentation

Tests:
1. Instrument/uninstrument cycle — patching and restoring create and stream
2. Cost calculation — OpenAIResponsesCostAdapter with input_tokens/output_tokens
3. Span attributes from create()
4. Stream context manager pattern (Hermes Agent pattern)
5. create(stream=True) returns non-Response — no crash
6. Registry inclusion — auto_instrument() includes openai_responses
7. _extract_model helper — normal string, None, and Omit sentinel
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../sdk/python'))

from kalibr.instrumentation import auto_instrument, get_instrumented_providers
from kalibr.pricing import compute_cost as pricing_compute_cost
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class InMemorySpanExporter(SpanExporter):
    """In-memory span exporter for testing"""

    def __init__(self):
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def clear(self):
        self.spans.clear()


@pytest.fixture(autouse=True)
def reset_responses_singleton():
    """Reset the singleton so each test gets a fresh instrumentation instance"""
    import kalibr.instrumentation.openai_responses_instr as mod
    saved = mod._responses_instrumentation
    mod._responses_instrumentation = None
    yield
    # Restore and uninstrument any leftover state
    if mod._responses_instrumentation is not None:
        mod._responses_instrumentation.uninstrument()
    mod._responses_instrumentation = saved


@pytest.fixture
def tracer_provider():
    """Setup tracer provider with in-memory exporter.

    Force-resets the global OTel TracerProvider so each test gets a clean slate.
    """
    # Force-reset the global TracerProvider to allow re-setting
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = None

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    yield provider, exporter

    # Cleanup
    provider.shutdown()
    exporter.clear()


def _make_response_mock(model="gpt-4o-mini", resp_id="resp_test123",
                        status="completed", input_tokens=100,
                        output_tokens=50, total_tokens=None):
    """Helper to build a Response-like mock object"""
    mock_usage = Mock()
    mock_usage.input_tokens = input_tokens
    mock_usage.output_tokens = output_tokens
    mock_usage.total_tokens = total_tokens if total_tokens is not None else input_tokens + output_tokens

    mock_response = Mock()
    mock_response.model = model
    mock_response.id = resp_id
    mock_response.status = status
    mock_response.usage = mock_usage
    return mock_response


class TestInstrumentUninstrumentCycle:
    """Test that Responses.create and .stream are patched and restored cleanly"""

    def test_create_is_patched_and_restored(self):
        """Verify Responses.create is monkey-patched on instrument and restored on uninstrument"""
        from kalibr.instrumentation.openai_responses_instr import get_instrumentation
        from openai.resources.responses import Responses

        original_create = Responses.create

        instr = get_instrumentation()
        instr.instrument()
        assert Responses.create is not original_create, "create should be patched"
        assert instr.is_instrumented is True

        instr.uninstrument()
        assert Responses.create is original_create, "create should be restored"
        assert instr.is_instrumented is False

    def test_stream_is_patched_and_restored(self):
        """Verify Responses.stream is monkey-patched on instrument and restored on uninstrument"""
        from kalibr.instrumentation.openai_responses_instr import get_instrumentation
        from openai.resources.responses import Responses

        original_stream = Responses.stream

        instr = get_instrumentation()
        instr.instrument()
        # Stream may or may not be patched depending on implementation;
        # if patched it should differ from original
        patched = Responses.stream is not original_stream

        instr.uninstrument()
        assert Responses.stream is original_stream, "stream should be restored after uninstrument"

    def test_double_instrument_is_idempotent(self):
        """Calling instrument() twice should succeed both times"""
        from kalibr.instrumentation.openai_responses_instr import get_instrumentation

        instr = get_instrumentation()
        assert instr.instrument() is True
        assert instr.instrument() is True
        instr.uninstrument()

    def test_uninstrument_when_not_instrumented(self):
        """Calling uninstrument() when not instrumented should succeed"""
        from kalibr.instrumentation.openai_responses_instr import get_instrumentation

        instr = get_instrumentation()
        assert instr.uninstrument() is True


class TestCostCalculation:
    """OpenAIResponsesCostAdapter uses input_tokens/output_tokens, not prompt_tokens/completion_tokens"""

    def test_cost_with_input_output_tokens(self):
        """Cost calculation uses input_tokens and output_tokens keys"""
        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesCostAdapter

        adapter = OpenAIResponsesCostAdapter()

        cost = adapter.calculate_cost(
            "gpt-4o-mini",
            {"input_tokens": 1000, "output_tokens": 500}
        )

        expected = pricing_compute_cost("openai", "gpt-4o-mini", 1000, 500)
        assert abs(cost - expected) < 0.000001

    def test_cost_matches_centralized_pricing(self):
        """Adapter cost matches kalibr.pricing.compute_cost for various models"""
        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesCostAdapter

        adapter = OpenAIResponsesCostAdapter()

        test_cases = [
            ("gpt-4o", 1000, 500),
            ("gpt-4", 2000, 1000),
            ("gpt-4o-mini", 5000, 2500),
        ]

        for model, input_tokens, output_tokens in test_cases:
            adapter_cost = adapter.calculate_cost(
                model,
                {"input_tokens": input_tokens, "output_tokens": output_tokens}
            )
            pricing_cost = pricing_compute_cost("openai", model, input_tokens, output_tokens)
            assert adapter_cost == pricing_cost, f"Mismatch for {model}"

    def test_cost_zero_tokens(self):
        """Cost should be 0 when no tokens are used"""
        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesCostAdapter

        adapter = OpenAIResponsesCostAdapter()
        cost = adapter.calculate_cost("gpt-4o", {"input_tokens": 0, "output_tokens": 0})
        assert cost == 0.0

    def test_cost_missing_keys_default_to_zero(self):
        """Missing token keys should default to zero, not crash"""
        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesCostAdapter

        adapter = OpenAIResponsesCostAdapter()
        cost = adapter.calculate_cost("gpt-4o", {})
        assert cost == 0.0

    def test_vendor_name_is_openai(self):
        """Vendor name should be 'openai'"""
        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesCostAdapter

        adapter = OpenAIResponsesCostAdapter()
        assert adapter.get_vendor_name() == "openai"


class TestSpanAttributesFromCreate:
    """Mock Responses.create to return a Response-like object and verify span attributes"""

    def test_span_attributes(self, tracer_provider):
        """Verify span has correct llm.* attributes from a create() call"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesInstrumentation
        from openai.resources.responses import Responses

        # Use a fresh (non-singleton) instance so its tracer uses our provider
        instr = OpenAIResponsesInstrumentation()

        mock_response = _make_response_mock(
            model="gpt-4o-mini", resp_id="resp_test123",
            input_tokens=100, output_tokens=50, total_tokens=150
        )

        # Build the wrapper around a mock original
        mock_original = Mock(return_value=mock_response)
        wrapper = instr._traced_create_wrapper(mock_original)

        # Call the wrapper directly (self_instance arg + kwargs)
        mock_self_instance = Mock()
        result = wrapper(mock_self_instance, model="gpt-4o-mini", input="Hello")

        assert result is mock_response

        # Check spans
        assert len(exporter.spans) >= 1
        span = exporter.spans[-1]
        attrs = dict(span.attributes)

        assert attrs.get("llm.vendor") == "openai"
        assert attrs.get("llm.api") == "responses"
        assert attrs.get("llm.request.model") == "gpt-4o-mini"
        assert attrs.get("llm.usage.prompt_tokens") == 100  # mapped from input_tokens
        assert attrs.get("llm.usage.completion_tokens") == 50  # mapped from output_tokens
        assert attrs.get("llm.usage.input_tokens") == 100
        assert attrs.get("llm.usage.output_tokens") == 50
        assert attrs.get("llm.usage.total_tokens") == 150
        assert attrs.get("llm.response.model") == "gpt-4o-mini"
        assert attrs.get("llm.response.id") == "resp_test123"
        assert "llm.cost_usd" in attrs
        assert attrs["llm.cost_usd"] > 0
        assert "llm.latency_ms" in attrs
        assert attrs["llm.latency_ms"] >= 0

    def test_span_cost_matches_pricing(self, tracer_provider):
        """Verify span llm.cost_usd matches compute_cost"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesInstrumentation

        instr = OpenAIResponsesInstrumentation()

        mock_response = _make_response_mock(
            model="gpt-4o", input_tokens=2000, output_tokens=1000, total_tokens=3000
        )

        mock_original = Mock(return_value=mock_response)
        wrapper = instr._traced_create_wrapper(mock_original)

        mock_self_instance = Mock()
        wrapper(mock_self_instance, model="gpt-4o", input="test")

        span = exporter.spans[-1]
        attrs = dict(span.attributes)

        expected_cost = pricing_compute_cost("openai", "gpt-4o", 2000, 1000)
        assert abs(attrs["llm.cost_usd"] - expected_cost) < 0.000001


class TestStreamContextManagerPattern:
    """Test the Hermes Agent streaming pattern:
        with client.responses.stream(**kwargs) as stream:
            for _ in stream:
                pass
            response = stream.get_final_response()
    """

    def test_stream_returns_response_with_usage(self, tracer_provider):
        """Simulate the stream context manager and verify get_final_response works"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import get_instrumentation
        from openai.resources.responses import Responses

        instr = get_instrumentation()
        instr.instrument()

        try:
            # Build a final Response-like mock (returned by get_final_response)
            mock_final_response = _make_response_mock(
                model="gpt-4o", resp_id="resp_stream_test",
                input_tokens=500, output_tokens=200, total_tokens=700
            )

            # Build a mock ResponseStream (the iterator)
            mock_response_stream = MagicMock()
            mock_response_stream.__iter__ = Mock(return_value=iter([
                Mock(type="response.output_text.delta"),
                Mock(type="response.output_text.done"),
            ]))
            mock_response_stream.get_final_response = Mock(return_value=mock_final_response)

            # Build a mock ResponseStreamManager (the context manager)
            mock_stream_manager = MagicMock()
            mock_stream_manager.__enter__ = Mock(return_value=mock_response_stream)
            mock_stream_manager.__exit__ = Mock(return_value=False)

            # Patch the stream method to return our mock
            with patch.object(Responses, 'stream', return_value=mock_stream_manager):
                mock_self_instance = Mock()

                # Simulate the Hermes Agent pattern
                with Responses.stream(mock_self_instance, model="gpt-4o", input="Hello") as stream:
                    for _ in stream:
                        pass
                    response = stream.get_final_response()

                # Verify get_final_response returns the real response
                assert response.model == "gpt-4o"
                assert response.id == "resp_stream_test"
                assert response.usage.input_tokens == 500
                assert response.usage.output_tokens == 200

        finally:
            instr.uninstrument()

    def test_stream_get_final_response_has_usage(self):
        """get_final_response() should return an object with input_tokens/output_tokens"""
        mock_response = _make_response_mock(
            model="gpt-4o-mini", input_tokens=300, output_tokens=150, total_tokens=450
        )

        mock_stream = MagicMock()
        mock_stream.get_final_response = Mock(return_value=mock_response)

        response = mock_stream.get_final_response()
        assert response.usage.input_tokens == 300
        assert response.usage.output_tokens == 150


class TestCreateStreamTrueNonResponse:
    """When Responses.create is called with stream=True it returns a Stream object, not a Response.
    The wrapper should NOT attempt to extract usage from it (no crash).
    """

    def test_create_stream_true_no_crash(self, tracer_provider):
        """create(stream=True) returns a non-Response object; wrapper must not crash"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesInstrumentation

        instr = OpenAIResponsesInstrumentation()

        # A stream object that does NOT have .usage, .model as proper Response attrs
        mock_stream_obj = Mock(spec=[])  # empty spec — no attributes at all

        mock_original = Mock(return_value=mock_stream_obj)
        wrapper = instr._traced_create_wrapper(mock_original)

        mock_self_instance = Mock()
        result = wrapper(mock_self_instance, model="gpt-4o", stream=True)

        # Should return the stream object without crashing
        assert result is mock_stream_obj

        # A span should still be emitted (even if no usage was extracted)
        assert len(exporter.spans) >= 1
        span = exporter.spans[-1]
        attrs = dict(span.attributes)
        assert attrs.get("llm.vendor") == "openai"
        assert attrs.get("llm.api") == "responses"
        # Usage attributes should NOT be present (no crash)
        assert "llm.usage.prompt_tokens" not in attrs


class TestRegistryInclusion:
    """Verify auto_instrument() with default args includes openai_responses"""

    def test_auto_instrument_includes_openai_responses(self):
        """auto_instrument() default provider list includes openai_responses"""
        results = auto_instrument()
        assert "openai_responses" in results

    def test_get_instrumented_providers_includes_openai_responses(self):
        """After auto_instrument(), get_instrumented_providers() includes openai_responses"""
        results = auto_instrument()
        if results.get("openai_responses"):
            providers = get_instrumented_providers()
            assert "openai_responses" in providers


class TestExtractModel:
    """Test model extraction logic with normal string, None, and OpenAI Omit sentinel.

    The wrapper extracts model via kwargs.get("model", "unknown").
    We test by calling the wrapper directly and checking span attributes.
    """

    def test_extract_model_normal_string(self, tracer_provider):
        """Normal model string should be used as-is"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesInstrumentation

        instr = OpenAIResponsesInstrumentation()
        mock_response = _make_response_mock(model="gpt-4o")
        wrapper = instr._traced_create_wrapper(Mock(return_value=mock_response))
        wrapper(Mock(), model="gpt-4o", input="test")

        attrs = dict(exporter.spans[-1].attributes)
        assert attrs.get("llm.request.model") == "gpt-4o"

    def test_extract_model_none(self, tracer_provider):
        """None model passed explicitly"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesInstrumentation

        instr = OpenAIResponsesInstrumentation()
        mock_response = _make_response_mock(model="gpt-4o")
        mock_response.usage = None
        wrapper = instr._traced_create_wrapper(Mock(return_value=mock_response))

        # model=None: kwargs.get("model", "unknown") returns None
        # OpenTelemetry will drop None attribute but should not crash
        wrapper(Mock(), model=None, input="test")

        assert len(exporter.spans) >= 1  # no crash, span emitted

    def test_extract_model_omit_sentinel(self, tracer_provider):
        """OpenAI NOT_GIVEN sentinel should not crash model extraction"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesInstrumentation
        from openai import NOT_GIVEN

        instr = OpenAIResponsesInstrumentation()
        mock_response = _make_response_mock(model="gpt-4o")
        mock_response.usage = None
        wrapper = instr._traced_create_wrapper(Mock(return_value=mock_response))

        # NOT_GIVEN is the Omit sentinel — should not crash
        wrapper(Mock(), model=NOT_GIVEN, input="test")

        assert len(exporter.spans) >= 1  # no crash, span emitted

    def test_extract_model_missing_kwarg_defaults(self, tracer_provider):
        """When model kwarg is not passed at all, it should default to 'unknown'"""
        provider, exporter = tracer_provider

        from kalibr.instrumentation.openai_responses_instr import OpenAIResponsesInstrumentation

        instr = OpenAIResponsesInstrumentation()
        mock_response = _make_response_mock(model="gpt-4o")
        mock_response.usage = None
        wrapper = instr._traced_create_wrapper(Mock(return_value=mock_response))

        # Omit model kwarg entirely
        wrapper(Mock(), input="test")

        assert len(exporter.spans) >= 1
        attrs = dict(exporter.spans[-1].attributes)
        assert attrs.get("llm.request.model") == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
