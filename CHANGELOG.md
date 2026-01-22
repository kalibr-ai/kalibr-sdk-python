# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
