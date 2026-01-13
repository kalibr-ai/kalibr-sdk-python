# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

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
