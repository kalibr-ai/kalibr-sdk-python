# Contributing to Kalibr Python SDK

Thank you for your interest in contributing to the Kalibr Python SDK! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We're building something together.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git

### Development Setup

1. Fork the repository on GitHub
2. Clone your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/kalibr-sdk-python.git
cd kalibr-sdk-python
```

3. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

4. Install the package in development mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

5. Set up your environment variables (copy from `.env.example`):

```bash
cp .env.example .env
# Edit .env with your configuration
```

## Making Changes

### Branch Naming

Create a descriptive branch for your changes:

```bash
git checkout -b feature/add-new-provider
git checkout -b fix/token-counting-bug
git checkout -b docs/update-readme
```

### Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting (line length: 100)
- **Ruff** for linting

Before committing, run:

```bash
black kalibr/
ruff check kalibr/
```

### Running Tests

Run the test suite with pytest:

```bash
pytest
```

For verbose output:

```bash
pytest -v
```

### Commit Messages

Write clear, concise commit messages:

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Fix bug" not "Fixes bug")
- Reference issues when applicable ("Fix token counting #123")

## Pull Requests

### Before Submitting

1. Ensure all tests pass
2. Run code formatting (`black`) and linting (`ruff`)
3. Update documentation if needed
4. Add tests for new functionality

### PR Process

1. Push your branch to your fork
2. Open a Pull Request against the `main` branch
3. Fill out the PR template with:
   - Description of changes
   - Related issue (if applicable)
   - Testing performed
4. Wait for review and address any feedback

## Reporting Issues

### Bug Reports

Include:
- Python version
- SDK version
- Steps to reproduce
- Expected vs actual behavior
- Error messages/stack traces

### Feature Requests

Include:
- Use case description
- Proposed solution (if any)
- Alternatives considered

## Areas for Contribution

We especially welcome contributions in:

- **New provider instrumentation** - Add support for additional LLM providers
- **Documentation** - Improve examples and guides
- **Bug fixes** - Help us squash bugs
- **Performance** - Optimize tracing overhead
- **Testing** - Increase test coverage

## Questions?

Feel free to open an issue for questions or reach out to the maintainers.

Thank you for contributing!
