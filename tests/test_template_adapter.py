"""Tests for the template adapter working example."""

from pathlib import Path

from bitegraph.adapters._template_adapter import TemplateAdapter


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "bitegraph"
    / "adapters"
    / "_template_adapter"
    / "fixtures"
    / "sample_order.csv"
)


def test_template_adapter_parse() -> None:
    adapter = TemplateAdapter()
    items = adapter.parse(FIXTURE.read_bytes(), {"source": "template_source"})
    assert len(items) == 2
    assert items[0].merchant_name == "Sample Restaurant"
    assert items[0].item_name_raw == "Burger"
