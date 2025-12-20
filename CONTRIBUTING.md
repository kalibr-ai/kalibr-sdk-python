# Contributing to Kalibr Python SDK

Thanks for your interest in contributing to the Kalibr Python SDK! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Style](#code-style)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Testing Guidelines](#testing-guidelines)
- [Adding a New Integration](#adding-a-new-integration)
- [Reporting Issues](#reporting-issues)
- [Security Issues](#security-issues)
- [Questions](#questions)
- [Code of Conduct](#code-of-conduct)
- [License](#license)

## Getting Started

1. **Fork the repository**

   Click the "Fork" button on [GitHub](https://github.com/kalibr-ai/kalibr-sdk-python)

2. **Clone your fork**

   ```bash
   git clone https://github.com/YOUR_USERNAME/kalibr-sdk-python.git
   cd kalibr-sdk-python
   ```

3. **Add upstream remote**

   ```bash
   git remote add upstream https://github.com/kalibr-ai/kalibr-sdk-python.git
   ```

4. **Create a branch**

   ```bash
   git checkout -b feat/your-feature-name
   ```

## Development Setup

### Install Dependencies

```bash
# Install in development mode with all optional dependencies
pip install -e ".[dev,all]"

# Or install with specific integrations
pip install -e ".[dev,langchain,crewai,openai-agents]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=kalibr --cov-report=html

# Run specific test file
pytest tests/test_instrumentation.py

# Run with verbose output
pytest -v
```

### Code Formatting

```bash
# Format code with Black (line length 100)
black kalibr/ tests/

# Check formatting without applying
black --check kalibr/ tests/
```

### Linting

```bash
# Run Ruff linter
ruff check kalibr/ tests/

# Auto-fix issues
ruff check --fix kalibr/ tests/
```

### Type Checking

```bash
# Run mypy for type checking
mypy kalibr/
```

## Project Structure

```
kalibr-sdk-python/
├── kalibr/                     # Core SDK
│   ├── __init__.py             # Package exports and auto-instrumentation
│   ├── intelligence.py         # KalibrIntelligence API client
│   ├── trace_capsule.py        # TraceCapsule for cross-agent context
│   ├── simple_tracer.py        # @trace decorator
│   ├── cost_adapter.py         # Multi-vendor cost calculation
│   ├── collector.py            # OpenTelemetry collector setup
│   ├── context.py              # Trace context management
│   ├── instrumentation/        # Auto-instrumentation modules
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── google.py
│   └── cli/                    # CLI commands
│       ├── main.py
│       ├── serve.py
│       ├── run.py
│       └── deploy_cmd.py
├── kalibr_langchain/           # LangChain integration
├── kalibr_crewai/              # CrewAI integration
├── kalibr_openai_agents/       # OpenAI Agents SDK integration
├── examples/                   # Usage examples
├── tests/                      # Test suite
├── pyproject.toml              # Project configuration
└── README.md
```

## Code Style

### Formatting

- **Black** for code formatting with line length of 100
- **Ruff** for linting

```bash
black --line-length 100 kalibr/
ruff check kalibr/
```

### Type Hints

Type hints are required for all public APIs:

```python
def get_policy(
    goal: str,
    optimize_for: str = "balanced",
    constraints: dict[str, Any] | None = None,
) -> PolicyResponse:
    """Get the optimal execution policy for a goal."""
    ...
```

### Docstrings

Use Google-style docstrings for all public functions and classes:

```python
def report_outcome(
    trace_id: str,
    goal: str,
    success: bool,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Report the outcome of an LLM execution for learning.

    This helps Kalibr improve model recommendations based on
    real-world success rates.

    Args:
        trace_id: The trace ID from the execution.
        goal: The goal that was attempted (e.g., "book_meeting").
        success: Whether the execution achieved the goal.
        metadata: Optional additional context about the execution.

    Raises:
        ValueError: If trace_id is empty.
        APIError: If the API request fails.

    Example:
        >>> from kalibr import report_outcome, get_trace_id
        >>> trace_id = get_trace_id()
        >>> report_outcome(trace_id, goal="summarize", success=True)
    """
    ...
```

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

| Prefix | Description |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes |
| `test:` | Adding or updating tests |
| `refactor:` | Code refactoring (no functional change) |
| `perf:` | Performance improvement |
| `chore:` | Maintenance tasks, dependencies, configs |

### Examples

```
feat: add streaming support to TraceCapsule
fix: handle empty response from Anthropic API
docs: update README with TraceCapsule examples
test: add unit tests for cost adapter
refactor: extract common logic into base instrumentor
perf: reduce memory allocation in span processing
chore: update OpenTelemetry dependencies to 1.21.0
```

## Pull Request Process

1. **Create a Pull Request**

   - Push your branch to your fork
   - Open a PR against `main` branch
   - Fill out the PR template completely

2. **PR Checklist**

   - [ ] Code follows the style guidelines
   - [ ] Tests pass locally (`pytest`)
   - [ ] New code has tests
   - [ ] Documentation is updated
   - [ ] Commit messages follow conventions

3. **Ensure CI Passes**

   All CI checks must pass before merging:
   - Tests (pytest)
   - Linting (ruff)
   - Formatting (black)
   - Type checking (mypy)

4. **Request Review**

   Request review from maintainers. Address feedback promptly.

## Testing Guidelines

### Writing Tests

```python
import pytest
from kalibr import trace, get_trace_id

class TestTraceDecorator:
    """Tests for the @trace decorator."""

    def test_trace_captures_operation(self):
        """Verify trace decorator captures operation name."""
        @trace(operation="test_op", provider="openai", model="gpt-4")
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

    def test_trace_with_exception(self):
        """Verify trace handles exceptions correctly."""
        @trace(operation="failing_op")
        def failing_function():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_function()

    @pytest.mark.asyncio
    async def test_async_trace(self):
        """Verify trace works with async functions."""
        @trace(operation="async_op")
        async def async_function():
            return "async result"

        result = await async_function()
        assert result == "async result"
```

### Test Organization

- Place tests in `tests/` directory
- Mirror the source structure (e.g., `tests/test_intelligence.py`)
- Use descriptive test names that explain behavior
- Group related tests in classes

## Adding a New Integration

To add support for a new framework (e.g., `kalibr_newframework`):

1. **Create the integration package**

   ```
   kalibr_newframework/
   ├── __init__.py
   ├── instrumentor.py
   └── README.md
   ```

2. **Implement the instrumentor**

   ```python
   # kalibr_newframework/instrumentor.py
   from kalibr import trace, get_or_create_capsule

   class KalibrNewFrameworkInstrumentor:
       """Instrumentor for NewFramework."""

       def __init__(self, api_key: str | None = None):
           self.api_key = api_key

       def instrument(self) -> None:
           """Enable instrumentation for NewFramework."""
           # Patch framework methods
           ...
   ```

3. **Add to pyproject.toml**

   ```toml
   [project.optional-dependencies]
   newframework = ["newframework>=1.0.0"]
   ```

4. **Add to setuptools packages**

   ```toml
   [tool.setuptools.packages.find]
   include = ["kalibr*", "kalibr_newframework*"]
   ```

5. **Write tests**

   Create `tests/test_newframework_integration.py`

6. **Add documentation**

   - Create `kalibr_newframework/README.md`
   - Add section to main README.md

## Reporting Issues

When reporting a bug, please include:

- **Python version**: `python --version`
- **SDK version**: `pip show kalibr`
- **Operating system**: e.g., macOS 14.0, Ubuntu 22.04
- **Reproduction code**: Minimal code that reproduces the issue
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Error messages**: Full stack trace if applicable

### Issue Template

```markdown
**Environment**
- Python: 3.11.5
- Kalibr SDK: 1.1.0
- OS: Ubuntu 22.04

**Reproduction**
```python
import kalibr
from openai import OpenAI
# minimal code here
```

**Expected**
Description of expected behavior

**Actual**
Description of actual behavior + error messages
```

## Security Issues

**Do not open public issues for security vulnerabilities.**

Please report security issues directly to:

📧 **security@kalibr.systems**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and work with you on a fix.

## Questions

For questions and discussions:

- **GitHub Discussions**: [github.com/kalibr-ai/kalibr-sdk-python/discussions](https://github.com/kalibr-ai/kalibr-sdk-python/discussions)
- **Email**: support@kalibr.systems
- **Documentation**: [docs.kalibr.systems](https://docs.kalibr.systems)

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

We are committed to providing a welcoming and inclusive environment for all contributors.

## License

By contributing to Kalibr Python SDK, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).

All contributions must be original work or properly attributed open source code compatible with Apache 2.0.
