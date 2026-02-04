"""Local CI runner that mirrors the GitHub Actions workflow."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, check=True, cwd=cwd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bitegraph-ci")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pip install steps (useful if deps already installed).",
    )
    args = parser.parse_args(argv)

    cwd = Path.cwd()
    python = sys.executable

    if not args.skip_install:
        _run([python, "-m", "pip", "install", "--upgrade", "pip"], cwd)
        _run([python, "-m", "pip", "install", "-e", ".[dev]"], cwd)

    _run([python, "-m", "ruff", "check", "src", "tests"], cwd)
    _run([python, "-m", "black", "--check", "src", "tests"], cwd)
    _run([python, "-m", "mypy", "src"], cwd)
    _run(
        [
            python,
            "-m",
            "pytest",
            "--cov=src/bitegraph",
            "--cov-report=term-missing",
            "--cov-report=xml",
        ],
        cwd,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
