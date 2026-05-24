# Backend Workflow Notes

Run commands from `backend/`.

## Docs policy check

This repo includes `scripts/check_docs_updated.py` to enforce that Markdown docs are
updated when implementation or configuration files change.

Run it manually with:

```powershell
make docs-check
```

To enable it before each commit:

```powershell
uv sync --extra dev --no-install-project
uv run pre-commit install
uv run pre-commit run --all-files
```

The pre-commit configuration lives in `backend/.pre-commit-config.yaml`, so install and
run `pre-commit` from the `backend/` directory.

## Hook behavior

The local hook configuration installs both `pre-commit` and `pre-push` hooks.

- `pre-commit` runs hygiene checks, the backend docs policy check, `ruff check --fix`,
  and `ruff format`
- `pre-push` runs `make check`

Use this before pushing:

```powershell
make check
```

## Backend-specific guidance

Backend-specific contributor rules live in `backend/AGENTS.md`. The repo-root
`AGENTS.md` remains the top-level guide for the whole repository.
