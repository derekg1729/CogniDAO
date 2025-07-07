# AGENTS Guidelines: infra_core

This directory contains the core infrastructure library.

Follow the repository [AGENTS.md](../AGENTS.md) for general rules. When working in `libs/infra_core`:

- Run the infra_core test suite before committing:

```bash
uv run tox -e infra_core
```

- Maintain the library's pyproject dependencies. Update tests when adding features.



