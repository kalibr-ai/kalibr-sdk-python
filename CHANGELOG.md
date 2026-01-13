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
