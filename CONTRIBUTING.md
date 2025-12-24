# Contributing to Kalibr Python SDK

Thanks for your interest in contributing to the Kalibr Python SDK! This document provides guidelines and instructions for contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/kalibr-sdk-python.git
   cd kalibr-sdk-python
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feat/my-new-feature
   ```

## Development Setup

### Prerequisites

- Python 3.9 or higher
- pip or uv for package management

### Installation

```bash
# Install in development mode with all dependencies
pip install -e ".[dev,langchain,crewai,openai-agents]"

# Or install just core dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=kalibr

# Run specific test file
pytest tests/test_intelligence.py
```

### Code Formatting

We use `black` for formatting and `ruff` for linting:

```bash
# Format code (line length: 100)
black kalibr/ --line-length 100

# Check linting
ruff check kalibr/

# Fix auto-fixable issues
ruff check kalibr/ --fix
```

### Type Checking

```bash
# Run mypy
mypy kalibr/
```

## Project Structure

```
kalibr-sdk-python/
├── kalibr/                    # Core SDK
│   ├── __init__.py           # Main exports
│   ├── client.py             # Kalibr client
│   ├── collector.py          # OpenTelemetry collector setup
│   ├── instrumentation.py    # Auto-instrumentation
│   ├── intelligence.py       # Intelligence API client
│   ├── trace_capsule.py      # TraceCapsule for cross-agent tracing
│   ├── simple_tracer.py      # @trace decorator
│   ├── cost_adapter.py       # Cost calculation adapters
│   └── cli/                   # CLI commands
├── kalibr_langchain/          # LangChain integration
├── kalibr_crewai/             # CrewAI integration
├── kalibr_openai_agents/      # OpenAI Agents SDK integration
├── tests/                     # Test suite
└── examples/                  # Example scripts
```

## Code Style

### General Guidelines

- Use type hints for all function parameters and return values
- Write docstrings in Google style format
- Keep functions focused and small
- Prefer explicit over implicit

### Docstring Example

```python
def get_policy(goal: str, constraints: dict | None = None) -> dict[str, Any]:
    """Get execution policy for a goal.

    Queries the Intelligence API for the optimal model and execution
    path based on historical outcome data.

    Args:
        goal: The goal to optimize for (e.g., "book_meeting").
        constraints: Optional constraints dict with keys like
            max_cost_usd, max_latency_ms, min_quality.

    Returns:
        Policy dict containing recommended_model, outcome_success_rate,
        confidence, and alternatives.

    Raises:
        httpx.HTTPStatusError: If the API returns an error.

    Example:
        >>> policy = get_policy(goal="resolve_ticket")
        >>> print(policy["recommended_model"])
        'gpt-4o'
    """
```

## Commit Messages

Use conventional commit prefixes:

| Prefix | Description |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes |
| `test:` | Adding or updating tests |
| `refactor:` | Code refactoring (no functional change) |
| `chore:` | Build, CI, or tooling changes |

Examples:
- `feat: add tenant_id parameter to get_policy`
- `fix: handle timeout in intelligence client`
- `docs: update README with TraceCapsule examples`

## Pull Request Process

1. **Update documentation** if you're changing public APIs
2. **Add tests** for new functionality
3. **Run the test suite** and ensure all tests pass
4. **Update CHANGELOG.md** if appropriate
5. **Create a PR** against the `main` branch
6. **Request review** from maintainers

### PR Title Format

Use the same format as commit messages:
- `feat: add new intelligence endpoint`
- `fix: resolve race condition in collector`

## Testing Guidelines

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_<module>.py`
- Use pytest fixtures for common setup
- Mock external API calls

### Test Example

```python
import pytest
from kalibr.intelligence import get_policy

def test_get_policy_returns_recommendation():
    """Test that get_policy returns a valid recommendation."""
    policy = get_policy(goal="test_goal")

    assert "recommended_model" in policy
    assert "outcome_success_rate" in policy
    assert 0 <= policy["outcome_success_rate"] <= 1
```

## Adding New Integrations

To add a new framework integration:

1. Create a new directory: `kalibr_<framework>/`
2. Add `__init__.py` with public exports
3. Add `README.md` with usage documentation
4. Add optional dependency in `pyproject.toml`
5. Add tests in `tests/test_<framework>.py`
6. Update main README.md with integration section

## Security Issues

If you discover a security vulnerability, please **do not** open a public issue. Instead, email support@kalibr.systems with details. We will respond promptly and work with you to address the issue.

## Questions and Support

- **GitHub Discussions**: For questions and feature requests
- **Email**: support@kalibr.systems
- **Documentation**: https://docs.kalibr.systems

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
