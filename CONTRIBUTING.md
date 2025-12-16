# Contributing

Thanks for your interest in contributing to the Kalibr Python SDK!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a branch for your changes
4. Make your changes
5. Run tests
6. Submit a pull request

## Development Setup

```bash
git clone https://github.com/kalibr-ai/kalibr-sdk-python.git
cd kalibr-sdk-python

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black kalibr/
ruff check kalibr/
```

## Code Style

- Use `black` for formatting
- Use `ruff` for linting
- Run formatters before committing

## Commit Messages

Use clear prefixes:
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation
- `test:` — Tests
- `refactor:` — Code refactoring

## Pull Requests

1. Create a PR against `main`
2. Ensure CI passes
3. Request review from maintainers

## Questions?

- Open a GitHub Discussion
- Email: support@kalibr.systems

## Code of Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
