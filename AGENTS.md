# AGENTS Guidelines

This repository uses **AGENTS.md** files to guide AI-assisted contributions. Follow these practices unless a nested `AGENTS.md` overrides them.

## Core Principles
- Follow the [CogniDAO Charter](CHARTER.md) and the git-cogni spirit guide.
- Keep changes minimal and purposeful. Complexity must be justified.
- Untested code is untrusted code. Add tests for all non-trivial changes.
- Commit messages are contracts: ensure each message accurately reflects its diff.

These principles are outlined in `data/memory_banks/core/main/guide_git-cogni.md` lines 22-38.

## Setup
Run the development setup script once to install dependencies and pre-commit hooks:

```bash
./scripts/setup_dev_environment.sh
```
or
```bash
uv sync --group dev --group integration 
```

## Linting
Run Ruff and other pre-commit checks before committing:

```bash
pre-commit run -a
```

## Testing
Execute the full test suite with [Tox](https://tox.wiki/) via `uv`:

```bash
uv run tox
```

You can run a specific suite with `uv run tox -e <env>`.
Valid environments right now include `infra_core`, `mcp_server`, `web_api`, `integration`, `graphs`, and `shared_utils`.

### ⚠️ Adding New Tests
**`conftest.py` and `tox.ini` both impact cross-environment parts of the project's test suite. Careful when touching them. If you do, ensure you run the full test suite after, 'uv run tox'. Any failures are your responsibility!**

## Pull Requests
- Reference lines in files when summarizing changes.
- Ensure tests pass and linting is clean.
- Keep each PR focused on a single topic.


