# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-12-19

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
- **CLI Commands**: `serve`, `run`, `deploy`, `capsule`, `version`
- Python 3.13 support

### Changed

- Updated OpenTelemetry dependencies to 1.20.0+
- Improved auto-instrumentation reliability
- Silent failures on import (no spam logs when SDKs aren't installed)

## [1.0.0] - 2024-10-01

### Added

- Initial release
- Auto-Instrumentation for OpenAI, Anthropic, and Google AI SDKs
- OpenTelemetry-compatible span emission
- `@trace` decorator for manual tracing
- Cost adapters for multi-vendor pricing
- Token monitoring across providers
- Python 3.9 - 3.12 support
