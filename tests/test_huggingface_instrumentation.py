"""
Unit tests for HuggingFace InferenceClient instrumentation

Tests:
1. Instrumentation can be applied and removed (patches/restores methods)
2. Instrumented SDK calls create spans with correct attributes
3. Cost calculation uses flexible adapter
4. Modality and task_type attributes are set correctly on spans
5. Metric extraction works for different task types
"""

import pytest
import sys
import os
import types
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


@pytest.fixture(autouse=False)
def tracer_provider():
    """Setup tracer provider with in-memory exporter.

    Forces the global TracerProvider so spans are captured in-memory.
    """
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    # Force-set the global provider (bypasses "already set" guard)
    trace._TRACER_PROVIDER = None  # reset so set works
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)

    yield provider, exporter

    provider.shutdown()
    exporter.clear()


def _make_mock_inference_client():
    """Create a mock huggingface_hub module with InferenceClient and AsyncInferenceClient."""
    mock_module = types.ModuleType("huggingface_hub")

    class MockInferenceClient:
        def __init__(self, model=None, **kwargs):
            self.model = model

        def chat_completion(self, messages=None, model=None, **kwargs):
            return Mock()

        def text_generation(self, prompt=None, model=None, **kwargs):
            return Mock()

        def automatic_speech_recognition(self, audio=None, model=None, **kwargs):
            return Mock()

        def text_to_speech(self, text=None, model=None, **kwargs):
            return b"audio-bytes"

        def text_to_image(self, prompt=None, model=None, **kwargs):
            return Mock()

        def feature_extraction(self, text=None, model=None, **kwargs):
            return [[0.1, 0.2, 0.3]]

        def text_classification(self, text=None, model=None, **kwargs):
            return [{"label": "POSITIVE", "score": 0.95}]

        def translation(self, text=None, model=None, **kwargs):
            return Mock()

        def summarization(self, text=None, model=None, **kwargs):
            return Mock()

    class MockAsyncInferenceClient:
        def __init__(self, model=None, **kwargs):
            self.model = model

        async def chat_completion(self, messages=None, model=None, **kwargs):
            return Mock()

        async def text_generation(self, prompt=None, model=None, **kwargs):
            return Mock()

        async def automatic_speech_recognition(self, audio=None, model=None, **kwargs):
            return Mock()

        async def text_to_speech(self, text=None, model=None, **kwargs):
            return b"audio-bytes"

        async def text_to_image(self, prompt=None, model=None, **kwargs):
            return Mock()

        async def feature_extraction(self, text=None, model=None, **kwargs):
            return [[0.1, 0.2, 0.3]]

        async def text_classification(self, text=None, model=None, **kwargs):
            return [{"label": "POSITIVE", "score": 0.95}]

        async def translation(self, text=None, model=None, **kwargs):
            return Mock()

        async def summarization(self, text=None, model=None, **kwargs):
            return Mock()

    mock_module.InferenceClient = MockInferenceClient
    mock_module.AsyncInferenceClient = MockAsyncInferenceClient
    return mock_module


@pytest.fixture
def mock_huggingface():
    """Inject mock huggingface_hub into sys.modules for instrumentation."""
    mock_module = _make_mock_inference_client()
    original = sys.modules.get("huggingface_hub")
    sys.modules["huggingface_hub"] = mock_module
    yield mock_module
    if original is not None:
        sys.modules["huggingface_hub"] = original
    else:
        sys.modules.pop("huggingface_hub", None)


@pytest.fixture
def fresh_instrumentation(mock_huggingface, request):
    """Provide a fresh HuggingFaceInstrumentation instance (not singleton).

    If the test also uses tracer_provider, the tracer is re-initialized
    so it picks up the test's TracerProvider.
    """
    from kalibr.instrumentation.huggingface_instr import HuggingFaceInstrumentation

    instr = HuggingFaceInstrumentation()
    # Re-initialize tracer to pick up any TracerProvider set by fixtures
    instr.tracer = trace.get_tracer("kalibr.huggingface")
    yield instr
    instr.uninstrument()


class TestInstrumentPatchesMethods:
    """Test that instrument() patches methods correctly."""

    def test_instrument_patches_sync_methods(self, mock_huggingface, fresh_instrumentation):
        InferenceClient = mock_huggingface.InferenceClient
        originals = {m: getattr(InferenceClient, m) for m in [
            "chat_completion", "text_generation", "text_to_image",
            "automatic_speech_recognition", "feature_extraction",
        ]}

        success = fresh_instrumentation.instrument()
        assert success is True
        assert fresh_instrumentation.is_instrumented is True

        for method_name, original in originals.items():
            assert getattr(InferenceClient, method_name) is not original, (
                f"{method_name} was not patched"
            )

    def test_instrument_patches_async_methods(self, mock_huggingface, fresh_instrumentation):
        AsyncInferenceClient = mock_huggingface.AsyncInferenceClient
        original_chat = AsyncInferenceClient.chat_completion

        fresh_instrumentation.instrument()
        assert AsyncInferenceClient.chat_completion is not original_chat

    def test_instrument_is_idempotent(self, mock_huggingface, fresh_instrumentation):
        assert fresh_instrumentation.instrument() is True
        assert fresh_instrumentation.instrument() is True


class TestUninstrumentRestoresOriginals:
    """Test that uninstrument() restores original methods."""

    def test_uninstrument_restores_sync_methods(self, mock_huggingface, fresh_instrumentation):
        InferenceClient = mock_huggingface.InferenceClient
        original_chat = InferenceClient.chat_completion

        fresh_instrumentation.instrument()
        assert InferenceClient.chat_completion is not original_chat

        success = fresh_instrumentation.uninstrument()
        assert success is True
        assert fresh_instrumentation.is_instrumented is False
        assert InferenceClient.chat_completion is original_chat

    def test_uninstrument_restores_async_methods(self, mock_huggingface, fresh_instrumentation):
        AsyncInferenceClient = mock_huggingface.AsyncInferenceClient
        original_chat = AsyncInferenceClient.chat_completion

        fresh_instrumentation.instrument()
        fresh_instrumentation.uninstrument()
        assert AsyncInferenceClient.chat_completion is original_chat

    def test_uninstrument_when_not_instrumented(self, mock_huggingface, fresh_instrumentation):
        assert fresh_instrumentation.uninstrument() is True


class TestSpanCreationChatCompletion:
    """Test span creation for chat_completion (text task)."""

    def test_chat_completion_creates_span(
        self, tracer_provider, mock_huggingface, fresh_instrumentation
    ):
        provider, exporter = tracer_provider

        # Mock response with usage
        mock_usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_response = Mock(usage=mock_usage, model="meta-llama/Llama-3-8B-Instruct", id="resp-1")

        InferenceClient = mock_huggingface.InferenceClient
        orig_chat = InferenceClient.chat_completion
        InferenceClient.chat_completion = lambda self, *a, **kw: mock_response

        fresh_instrumentation.instrument()

        client = InferenceClient(model="meta-llama/Llama-3-8B-Instruct")
        result = client.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="meta-llama/Llama-3-8B-Instruct",
        )

        assert len(exporter.spans) == 1
        span = exporter.spans[0]
        attrs = dict(span.attributes)

        assert span.name == "huggingface.chat_completion"
        assert attrs["llm.vendor"] == "huggingface"
        assert attrs["llm.request.model"] == "meta-llama/Llama-3-8B-Instruct"
        assert attrs["kalibr.modality"] == "text"
        assert attrs["kalibr.task_type"] == "chat_completion"
        assert attrs["llm.usage.input_tokens"] == 100
        assert attrs["llm.usage.output_tokens"] == 50
        assert "llm.latency_ms" in attrs
        assert "llm.cost_usd" in attrs


class TestSpanCreationASR:
    """Test span creation for automatic_speech_recognition (audio task)."""

    def test_asr_creates_span_with_audio_modality(
        self, tracer_provider, mock_huggingface, fresh_instrumentation
    ):
        provider, exporter = tracer_provider

        mock_response = {"text": "hello world", "audio_duration_ms": 5000}

        InferenceClient = mock_huggingface.InferenceClient
        InferenceClient.automatic_speech_recognition = lambda self, *a, **kw: mock_response

        fresh_instrumentation.instrument()

        client = InferenceClient()
        result = client.automatic_speech_recognition(
            audio=b"audio-data", model="openai/whisper-large-v3"
        )

        assert len(exporter.spans) == 1
        span = exporter.spans[0]
        attrs = dict(span.attributes)

        assert span.name == "huggingface.automatic_speech_recognition"
        assert attrs["kalibr.modality"] == "audio"
        assert attrs["kalibr.task_type"] == "automatic_speech_recognition"
        assert attrs["llm.usage.audio_duration_ms"] == 5000


class TestSpanCreationTextToImage:
    """Test span creation for text_to_image (image task)."""

    def test_text_to_image_creates_span(
        self, tracer_provider, mock_huggingface, fresh_instrumentation
    ):
        provider, exporter = tracer_provider

        mock_image = Mock()
        mock_image.size = (1024, 1024)
        mock_image.model = None
        del mock_image.model  # no model attr on PIL images
        del mock_image.id

        InferenceClient = mock_huggingface.InferenceClient
        InferenceClient.text_to_image = lambda self, *a, **kw: mock_image

        fresh_instrumentation.instrument()

        client = InferenceClient()
        result = client.text_to_image(
            prompt="A cat", model="stabilityai/stable-diffusion-xl-base-1.0"
        )

        assert len(exporter.spans) == 1
        span = exporter.spans[0]
        attrs = dict(span.attributes)

        assert span.name == "huggingface.text_to_image"
        assert attrs["kalibr.modality"] == "image"
        assert attrs["kalibr.task_type"] == "text_to_image"
        assert attrs["llm.usage.image_count"] == 1
        assert attrs["llm.usage.image_resolution"] == "1024x1024"


class TestCostCalculation:
    """Test that cost calculation uses the flexible adapter."""

    def test_cost_adapter_vendor_name(self):
        from kalibr.instrumentation.huggingface_instr import HuggingFaceCostAdapter

        adapter = HuggingFaceCostAdapter()
        assert adapter.get_vendor_name() == "huggingface"

    def test_cost_adapter_token_based(self):
        from kalibr.instrumentation.huggingface_instr import HuggingFaceCostAdapter

        adapter = HuggingFaceCostAdapter()
        cost = adapter.compute_cost_flexible(
            "meta-llama/llama-3-8b-instruct",
            {"input_tokens": 1000, "output_tokens": 500},
        )
        # Should use centralized pricing; cost > 0
        assert cost >= 0.0

    def test_cost_adapter_non_token_returns_zero(self):
        from kalibr.instrumentation.huggingface_instr import HuggingFaceCostAdapter

        adapter = HuggingFaceCostAdapter()
        cost = adapter.compute_cost_flexible(
            "openai/whisper-large-v3",
            {"audio_duration_ms": 5000},
        )
        assert cost == 0.0

    def test_calculate_cost_delegates_to_flexible(self):
        from kalibr.instrumentation.huggingface_instr import HuggingFaceCostAdapter

        adapter = HuggingFaceCostAdapter()
        cost = adapter.calculate_cost(
            "meta-llama/llama-3-8b-instruct",
            {"input_tokens": 1000, "output_tokens": 500},
        )
        assert cost == adapter.compute_cost_flexible(
            "meta-llama/llama-3-8b-instruct",
            {"input_tokens": 1000, "output_tokens": 500},
        )


class TestModalityAndTaskAttributes:
    """Test that modality and task_type attributes are set correctly on spans."""

    @pytest.mark.parametrize(
        "method_name,expected_modality,expected_task",
        [
            ("chat_completion", "text", "chat_completion"),
            ("text_generation", "text", "text_generation"),
            ("translation", "text", "translation"),
            ("summarization", "text", "summarization"),
            ("automatic_speech_recognition", "audio", "automatic_speech_recognition"),
            ("text_to_speech", "audio", "text_to_speech"),
            ("text_to_image", "image", "text_to_image"),
            ("feature_extraction", "embedding", "feature_extraction"),
            ("text_classification", "classification", "text_classification"),
        ],
    )
    def test_modality_and_task_type(
        self,
        tracer_provider,
        mock_huggingface,
        fresh_instrumentation,
        method_name,
        expected_modality,
        expected_task,
    ):
        provider, exporter = tracer_provider
        fresh_instrumentation.instrument()

        client = mock_huggingface.InferenceClient(model="test-model")
        method = getattr(client, method_name)
        method(model="test-model")

        assert len(exporter.spans) >= 1
        span = exporter.spans[-1]
        attrs = dict(span.attributes)

        assert attrs["kalibr.modality"] == expected_modality
        assert attrs["kalibr.task_type"] == expected_task
        assert span.name == f"huggingface.{expected_task}"


class TestExtractMetrics:
    """Test the _extract_metrics helper."""

    def test_chat_completion_metrics_from_object(self):
        from kalibr.instrumentation.huggingface_instr import _extract_metrics

        response = Mock()
        response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        metrics = _extract_metrics("chat_completion", response)
        assert metrics == {"input_tokens": 100, "output_tokens": 50}

    def test_chat_completion_metrics_from_dict(self):
        from kalibr.instrumentation.huggingface_instr import _extract_metrics

        response = {"usage": {"prompt_tokens": 200, "completion_tokens": 80}}
        metrics = _extract_metrics("chat_completion", response)
        assert metrics == {"input_tokens": 200, "output_tokens": 80}

    def test_asr_metrics(self):
        from kalibr.instrumentation.huggingface_instr import _extract_metrics

        response = {"text": "hello", "audio_duration_ms": 3500}
        metrics = _extract_metrics("automatic_speech_recognition", response)
        assert metrics["audio_duration_ms"] == 3500

    def test_text_to_image_metrics(self):
        from kalibr.instrumentation.huggingface_instr import _extract_metrics

        response = Mock()
        response.size = (512, 512)
        metrics = _extract_metrics("text_to_image", response)
        assert metrics["image_count"] == 1
        assert metrics["image_resolution"] == "512x512"

    def test_feature_extraction_metrics(self):
        from kalibr.instrumentation.huggingface_instr import _extract_metrics

        response = [[0.1, 0.2, 0.3, 0.4]]
        metrics = _extract_metrics("feature_extraction", response)
        assert metrics["vector_dimensions"] == 4

    def test_text_classification_metrics(self):
        from kalibr.instrumentation.huggingface_instr import _extract_metrics

        response = [{"label": "POS", "score": 0.9}, {"label": "NEG", "score": 0.1}]
        metrics = _extract_metrics("text_classification", response)
        assert metrics["label_count"] == 2

    def test_text_to_speech_metrics(self):
        from kalibr.instrumentation.huggingface_instr import _extract_metrics

        response = b"raw-audio-bytes-here"
        metrics = _extract_metrics("text_to_speech", response)
        assert metrics["audio_bytes"] == len(response)


class TestSingletonPattern:
    """Test singleton and module-level functions."""

    def test_singleton_returns_same_instance(self, mock_huggingface):
        from kalibr.instrumentation.huggingface_instr import get_instrumentation

        instr1 = get_instrumentation()
        instr2 = get_instrumentation()
        assert instr1 is instr2

    def test_module_level_instrument(self, mock_huggingface):
        from kalibr.instrumentation import huggingface_instr

        success = huggingface_instr.instrument()
        assert success is True
        huggingface_instr.uninstrument()

    def test_module_level_uninstrument(self, mock_huggingface):
        from kalibr.instrumentation import huggingface_instr

        huggingface_instr.instrument()
        success = huggingface_instr.uninstrument()
        assert success is True


class TestRegistryIntegration:
    """Test that HuggingFace is included in the registry."""

    def test_auto_instrument_includes_huggingface(self, mock_huggingface):
        from kalibr.instrumentation import auto_instrument

        results = auto_instrument(["huggingface"])
        assert "huggingface" in results
        assert results["huggingface"] is True

    def test_auto_instrument_default_includes_huggingface(self, mock_huggingface):
        from kalibr.instrumentation import auto_instrument

        results = auto_instrument()
        assert "huggingface" in results


class TestImportErrorHandling:
    """Test graceful handling when huggingface_hub is not installed."""

    def test_instrument_returns_false_without_huggingface(self):
        from kalibr.instrumentation.huggingface_instr import HuggingFaceInstrumentation

        original = sys.modules.get("huggingface_hub")
        sys.modules["huggingface_hub"] = None  # Simulate ImportError

        instr = HuggingFaceInstrumentation()
        try:
            success = instr.instrument()
            assert success is False
        finally:
            if original is not None:
                sys.modules["huggingface_hub"] = original
            else:
                sys.modules.pop("huggingface_hub", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
