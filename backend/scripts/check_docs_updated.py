"""Require Markdown updates when repo behavior/config/code changes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DOC_EXTENSIONS = {".md", ".mdx"}
WATCHED_EXTENSIONS = {".py", ".toml", ".yaml", ".yml"}
WATCHED_FILENAMES = {"Makefile", ".env.example", ".pre-commit-config.yaml"}
IGNORED_PREFIXES = {".git/", ".venv/", ".pytest_cache/", ".ruff_cache/"}


def main(argv: list[str]) -> int:
    """Validate that changed implementation/config files include a Markdown update."""
    changed_files = _changed_files(argv)
    if not changed_files:
        return 0

    docs_changed = [path for path in changed_files if _is_markdown(path)]
    watched_changed = [path for path in changed_files if _is_watched(path)]
    if not watched_changed or docs_changed:
        return 0

    print(
        "Markdown docs must be updated when implementation, config, tests, examples, or workflow files change.\n"
        "Update README.md, AGENTS.md, docs/*.md, or another relevant Markdown file in the same change.",
        file=sys.stderr,
    )
    return 1


def _changed_files(argv: list[str]) -> list[Path]:
    raw_paths = argv or _git_changed_files()
    paths = []
    for raw_path in raw_paths:
        path = Path(raw_path)
        normalized = path.as_posix()
        if not normalized or any(normalized.startswith(prefix) for prefix in IGNORED_PREFIXES):
            continue
        if path.exists() or argv:
            paths.append(path)
    return paths


def _git_changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_markdown(path: Path) -> bool:
    return path.suffix.lower() in DOC_EXTENSIONS


def _is_watched(path: Path) -> bool:
    if path.name in WATCHED_FILENAMES:
        return True
    if path.suffix.lower() in WATCHED_EXTENSIONS:
        return True
    return path.parts[:1] in {("app",), ("tests",), ("examples",), ("scripts",), (".github",)}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
