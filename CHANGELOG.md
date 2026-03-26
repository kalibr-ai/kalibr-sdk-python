# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.8.0] - 2026-03-26

### Added

- **kalibr init — HuggingFace support** ([#121](https://github.com/kalibr-ai/kalibr-sdk-python/pull/121))
  - Scanner detects all 17 HuggingFace InferenceClient task methods and `pipeline()` calls
  - Rewriter generates `router.execute(task=..., input_data=...)` for HF tasks — correct method, not `completion()`
  - Task-appropriate default model pairs for all 17 task types
  - `router.execute()` `task_method_map` expanded from 10 to 17 tasks (was missing: `chat_completion`, `text_generation`, `token_classification`, `fill_mask`, `audio_classification`, `image_segmentation`, `table_question_answering`)
  - All scaffolded Routers now include 2 default paths (was 0 — defeats Thompson Sampling)
  - `import kalibr` enforced as first line in all generated code

- **HF token + DeepSeek provider** ([#123](https://github.com/kalibr-ai/kalibr-sdk-python/pull/123))
  - `HF_API_TOKEN` / `HUGGING_FACE_HUB_TOKEN` passed to `InferenceClient`
  - `deepseek-*` models recognized in `router._dispatch()` — no longer falls through to OpenAI

- **DeepSeek pricing + vendor attribution** ([#124](https://github.com/kalibr-ai/kalibr-sdk-python/pull/124))
  - `deepseek` vendor added to `pricing.py` (`deepseek-chat` $0.27/$1.10, `deepseek-reasoner` $0.55/$2.19, `deepseek-coder` $0.27/$1.10)
  - `_detect_vendor()` in `openai_instr.py`: DeepSeek calls get correct span name (`deepseek.chat.completions.create`), `llm.vendor=deepseek`, and DeepSeek pricing — no separate instrumentor needed

## [1.7.0] - 2026-03-18

### Added

- **Multimodal foundation** — Any model, any modality. Text LLMs, voice, image, embeddings, classification, translation
- **HuggingFace InferenceClient instrumentation** — All 17 task types auto-instrumented (chat_completion, text_generation, automatic_speech_recognition, text_to_speech, text_to_image, feature_extraction, text_classification, token_classification, fill_mask, audio_classification, image_to_text, image_classification, image_segmentation, object_detection, translation, summarization, table_question_answering)
- **Router.execute()** — Route any HuggingFace task with the same outcome-learning loop as Router.completion()
- **Unified pricing** — UNIT_PRICING supports tokens, audio_seconds, characters, and images through compute_cost_flexible()
- **Multimodal trace schema** — TraceEvent supports audio_duration_ms, audio_format, image_count, image_resolution, modality, task_type, unit_type
- **FlexibleCostAdapter** — Base class for cost adapters across any billing unit
- **14 intelligence task types**: transcribe, synthesize, image_gen, image_classify, embed, translate (new) + code, summarize, classify, generate, extract, qa, chat, general (existing)

### Fixed

- ElevenLabs pricing corrected (was 10x too low)
- Deepgram pricing corrected (per-minute price was in per-second field, 60x too high)
- OpenAI voice models (tts-1, tts-1-hd, whisper-1) added to UNIT_PRICING
- HuggingFace cost adapter now delegates to centralized pricing for non-token models

## [1.6.0] - 2026-03-11

### Added

- OpenAI Responses API instrumentation (`client.responses.create()` and `client.responses.stream()`)
- Automatic telemetry capture for agents using the Responses API (e.g., Hermes Agent in codex_responses mode)
- `openai_responses` provider in auto_instrument defaults — enabled automatically on `import kalibr`
- Stream context manager wrapping — captures usage/cost/latency from `get_final_response()` after stream completion

## [1.4.2] - 2026-02-04

### Fixed

- Fixed version string in __init__.py (was showing 1.2.7 instead of 1.4.1)

## [1.4.1] - 2026-02-04

### Fixed

- Fixed tools parameter bug where None was passed to Anthropic/OpenAI APIs
- Router now properly validates tools parameter before API calls

## [1.4.0] - 2026-02-02

### Added

- **In-request fallback for graceful degradation** ([#73](https://github.com/kalibr-ai/kalibr-sdk-python/pull/73))
  - Router now tries remaining registered paths when primary path fails
  - Eliminates user-visible errors during provider outages
  - When OpenAI/Anthropic/Google experiences an outage, SDK automatically tries backup paths
  - All failures still reported to intelligence service for Thompson Sampling learning
  - Preserves intelligent routing - this is a defensive safety net on top of Thompson Sampling

### Fixed

- **Critical: Memory Leak - HTTP Clients Created But Never Closed** ([#38](https://github.com/kalibr-ai/kalibr-sdk-python/issues/38))
  - Fixed resource leaks in convenience functions when using custom `tenant_id`
  - `get_policy()`, `report_outcome()`, `register_path()`, and `decide()` now properly close HTTP clients
  - All functions now use context manager pattern for temporary clients
  - Prevents connection exhaustion in long-running multi-tenant applications
  - Added comprehensive tests to verify proper resource cleanup (10 tests)
- **Critical: Thread-Safety Issues in Singleton Patterns and Shared State** ([#30](https://github.com/kalibr-ai/kalibr-sdk-python/issues/30))
  - Fixed race conditions in singleton patterns using double-checked locking
  - Added thread-safe locks to Intelligence client singleton (`kalibr/intelligence.py`)
  - Added thread-safe locks to all instrumentation singletons (OpenAI, Anthropic, Google)
  - Added thread-safe locks to collector setup/shutdown (`kalibr/collector.py`)
  - Added instance-level lock to `TraceCapsule.append_hop()` for concurrent mutations
  - Added module-level lock to instrumentation registry (`kalibr/instrumentation/registry.py`)
  - All singleton patterns now use double-checked locking to prevent multiple instances
  - All shared state operations are now protected by appropriate locks
  - SDK is now safe to use in multi-threaded applications (FastAPI, async frameworks, concurrent workers)

### Added

- **Helpful error messages for missing credentials**: Router now validates KALIBR_API_KEY and KALIBR_TENANT_ID on initialization and provides clear error messages with links to the dashboard settings page
- Comprehensive thread-safety test suite (`tests/test_thread_safety.py`)
  - Tests for concurrent singleton creation (all patterns)
  - Tests for concurrent TraceCapsule operations
  - Tests for concurrent instrumentation registration
  - Stress tests with 100+ threads and 1000+ operations
  - Reproduction test for issue #30 scenario
- **Critical: Duplicate Cost Adapter Implementations** ([#29](https://github.com/kalibr-ai/kalibr-sdk-python/issues/29))
  - Fixed inconsistent cost calculations caused by multiple implementations with different pricing units (per-1M, per-1K, per-token)
  - Created centralized pricing module (`kalibr.pricing`) as single source of truth for all model pricing
  - Standardized all pricing to per-1M tokens (matching OpenAI/Anthropic pricing pages)
  - Refactored `kalibr.cost_adapter`, `kalibr.instrumentation.base`, and all vendor-specific instrumentation files to use centralized pricing
  - Updated `simple_tracer.py` to use centralized cost calculation
  - Added comprehensive tests for pricing consistency across all adapters
  - Cost tracking is now reliable and consistent across all tracing methods

### Added

- New `kalibr.pricing` module with centralized pricing data and utilities
  - `get_pricing(vendor, model)` - Get pricing for any vendor/model
  - `normalize_model_name(vendor, model)` - Standardize model names with fuzzy matching
  - `compute_cost(vendor, model, input_tokens, output_tokens)` - Compute cost from centralized pricing
- Comprehensive test suite for pricing (`tests/test_pricing.py`, `tests/test_cost_adapter.py`)
- Consistency tests to ensure all adapters produce identical costs for same inputs

## [1.2.0] - 2024-12-23

### Added

- **Outcome-Conditioned Routing**: Intelligence API for querying optimal models based on historical success rates
  - `get_policy()` - Get best execution path for a goal
  - `report_outcome()` - Report execution results to improve recommendations
  - `KalibrIntelligence` class for direct API access
- **TraceCapsule**: Cross-agent context propagation for multi-agent systems
  - Rolling window of last 5 hops for compact HTTP headers
  - Aggregate cost and latency tracking across agent hops
- **Framework Integrations**:
  - LangChain (`kalibr_langchain`)
  - CrewAI (`kalibr_crewai`)
  - OpenAI Agents SDK (`kalibr_openai_agents`)
- CLI Commands: serve, run, deploy, capsule, version
- Python 3.13 support

### Changed

- Updated OpenTelemetry dependencies to 1.20.0+
- Improved auto-instrumentation reliability

## [1.0.0] - 2024-10-01

### Added

- Initial release
- Auto-instrumentation for OpenAI, Anthropic, Google AI SDKs
- @trace decorator for manual tracing
- Cost adapters for multi-vendor pricing
