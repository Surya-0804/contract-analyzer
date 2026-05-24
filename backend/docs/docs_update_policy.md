# Docs Update Policy

The backend includes [`scripts/check_docs_updated.py`](D:\Developement\contract-analyzer\backend\scripts\check_docs_updated.py) to enforce a simple rule:

- if implementation or configuration changes,
- the same change should include a Markdown documentation update.

## What the script checks

The script looks at changed files and separates them into two groups:

- Markdown docs
- watched implementation or workflow files

If watched files changed and no Markdown file changed in the same diff, the script exits
with status code `1` and prints a failure message.

If no watched files changed, or at least one Markdown file changed, it exits with `0`.

## What counts as documentation

These extensions count as docs updates:

- `.md`
- `.mdx`

Examples:

- `README.md`
- `AGENTS.md`
- files under `docs/`

## What files are watched

The script treats these as documentation-requiring changes:

- any `*.py`
- any `*.toml`
- any `*.yaml`
- any `*.yml`
- `Makefile`
- `.env.example`
- `.pre-commit-config.yaml`
- anything under:
  - `app/`
  - `tests/`
  - `examples/`
  - `scripts/`
  - `.github/`

## Ignored paths

These path prefixes are ignored:

- `.git/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`

## How the script gets changed files

There are two modes:

### 1. Explicit file list

If file paths are passed as command-line arguments, the script checks those paths.

Example:

```powershell
uv run python scripts/check_docs_updated.py app/api/routes/analyze.py README.md
```

This is the mode used by pre-commit when `pass_filenames: true`.

### 2. Git diff mode

If no file arguments are passed, the script runs:

```bash
git diff --name-only HEAD
```

It then validates the current working diff.

Example:

```powershell
uv run python scripts/check_docs_updated.py
```

## Local usage

From `backend/`:

```powershell
make docs-check
```

That runs:

```powershell
uv run python scripts/check_docs_updated.py
```

## Hook usage

The backend pre-commit configuration also runs this script before commit.

Current behavior:

- `pre-commit` passes changed filenames into the script
- `pre-push` does not run this script directly; it runs `make check`

## Failure message

When the rule fails, the script tells you to update a Markdown file in the same change,
for example:

- `README.md`
- `AGENTS.md`
- a file under `docs/`

## When to update docs

You should update docs when changing:

- API behavior
- prompts or pipeline stages
- environment variables or config
- developer workflow
- scripts or quality gates

## Limitations

- The script checks whether some Markdown changed, not whether the exact right doc changed.
- In Git diff mode, it depends on `git diff --name-only HEAD` working correctly.
- It is a policy check, not a semantic docs review.
