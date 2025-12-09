# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- License changed from MIT to Apache 2.0
- Default endpoints now point to hosted Kalibr service
- Removed FastAPI wrapper from public API (internal only)

### Removed
- Internal documentation and experimental examples

## [0.1.0] - 2025

### Added
- Auto-instrumentation for OpenAI, Anthropic, Google AI
- LangChain integration (kalibr-langchain)
- CrewAI integration (kalibr-crewai)
- OpenAI Agents SDK integration (kalibr-openai-agents)
- Cost tracking and token monitoring
- Trace context propagation
- TraceCapsule for cross-service tracing
