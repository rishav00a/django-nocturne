# Contributing to django-nocturne

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/rishav00a/django-nocturne
cd django-nocturne
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ollama]"
cd example_project
python manage.py migrate
python manage.py generate_demo_logs
```

## Running Tests

```bash
pytest tests/ -v
```

For coverage:
```bash
coverage run -m pytest tests/
coverage report
```

## Code Style

This project uses no external linter configuration. Please:
- Follow existing code style (no type annotations required but welcome)
- Keep functions focused; no premature abstraction
- Write tests for any new behaviour

## Pull Request Guidelines

1. Fork the repository and create a feature branch from `main`
2. Add tests for new functionality
3. Ensure `pytest tests/` passes
4. Update `CHANGELOG.md` under `[Unreleased]`
5. Open a pull request with a clear description

## Reporting Bugs

Open an issue at https://github.com/rishav00a/django-nocturne/issues with:
- Django and Python version
- Minimal reproduction steps
- Expected vs. actual behaviour

## Adding an AI Backend

1. Add a new branch in `nocturne/ai_diagnosis.py::_get_llm()`
2. Add the optional dependency in `pyproject.toml` under `[project.optional-dependencies]`
3. Document it in `docs/ai-backends.rst` and `README.md`
