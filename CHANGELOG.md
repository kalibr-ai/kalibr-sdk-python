# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

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
