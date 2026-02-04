# Contributing to BiteGraph

Thank you for your interest in contributing! This guide explains how to set up your environment and submit changes.

## Code of Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Development Setup

### Requirements

- Python 3.10+
- `pip` or `uv`

### Install

```bash
git clone https://github.com/FlavCliq/bitegraph.git
cd bitegraph

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Testing

```bash
pytest                          # Run all tests
pytest --cov                    # With coverage
pytest tests/test_models.py     # Single file
```

### Code Quality

```bash
black src tests                 # Format
isort src tests                 # Sort imports
ruff check src tests            # Lint
mypy src                        # Type check
```

## Adding a New Adapter

1. Create a directory under `src/bitegraph/adapters/<adapter_name>/`
2. Implement the `Adapter` protocol in `adapter.py`
3. Add synthetic fixtures in `fixtures/`
4. Add a `README.md` explaining the adapter
5. Write tests in `tests/adapters/test_<adapter_name>.py`
6. Update the main registry in `core/registry.py`

See `src/bitegraph/adapters/_template_adapter/` for a complete skeleton.

## Submitting Changes

1. Fork the repo and create a feature branch
2. Make your changes (keep commits focused)
3. Run tests and quality checks
4. Submit a pull request with a clear description

## Security Issues

Please do NOT open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md).

## Questions?

Open a discussion or issue on GitHub.
