"""Ensure fixtures stay small and synthetic."""

from pathlib import Path

MAX_BYTES = 50_000


def test_fixture_sizes() -> None:
    fixtures = Path(__file__).resolve().parents[1] / "src" / "bitegraph" / "adapters"
    for path in fixtures.rglob("fixtures/*"):
        if path.is_file():
            assert path.stat().st_size <= MAX_BYTES, f"Fixture too large: {path}"
