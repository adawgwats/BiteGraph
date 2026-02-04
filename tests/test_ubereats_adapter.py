"""Tests for Uber Eats adapter."""

from pathlib import Path

import pytest

from bitegraph.adapters.ubereats import UberEatsAdapter


FIXTURES = Path(__file__).resolve().parents[1] / "src" / "bitegraph" / "adapters" / "ubereats" / "fixtures"


def _read_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture()
def adapter() -> UberEatsAdapter:
    return UberEatsAdapter()


def test_parse_simple_order(adapter: UberEatsAdapter) -> None:
    items = adapter.parse(_read_fixture("simple_order.csv"), {"source": "uber_eats"})
    assert len(items) == 2
    assert items[0].merchant_name == "Sample Diner"
    assert items[0].item_name_raw == "Burger"


def test_parse_with_modifiers(adapter: UberEatsAdapter) -> None:
    items = adapter.parse(_read_fixture("order_with_modifiers.csv"), {"source": "uber_eats"})
    assert len(items) == 1
    assert items[0].modifiers_raw == ["White Rice", "Extra Portion", "No Cheese"]


def test_missing_columns(adapter: UberEatsAdapter) -> None:
    items = adapter.parse(_read_fixture("missing_columns.csv"), {"source": "uber_eats"})
    assert len(items) == 1
    assert items[0].merchant_name == "Sample Market"
    assert items[0].item_name_raw == "Spinach Salad"


def test_parse_multiple_orders(adapter: UberEatsAdapter) -> None:
    items = adapter.parse(_read_fixture("multiple_orders.csv"), {"source": "uber_eats"})
    assert len(items) == 3


def test_idempotent_event_id(adapter: UberEatsAdapter) -> None:
    items1 = adapter.parse(_read_fixture("simple_order.csv"), {"source": "uber_eats"})
    items2 = adapter.parse(_read_fixture("simple_order.csv"), {"source": "uber_eats"})
    assert items1[0].event_id == items2[0].event_id


def test_filter_non_completed(adapter: UberEatsAdapter) -> None:
    raw = (
        "Restaurant_Name,Request_Time_Local,Order_Status,Item_Name,Item_quantity,Item_Price,Order_Price,Currency\n"
        "Test Place,2026-01-01T12:00:00Z,canceled,Burger,1,5.00,5.00,USD\n"
        "Test Place,2026-01-01T12:00:00Z,completed,Burger,1,5.00,5.00,USD\n"
    ).encode("utf-8")
    items = adapter.parse(raw, {"source": "uber_eats"})
    assert len(items) == 1
    items_all = adapter.parse(raw, {"source": "uber_eats", "include_non_completed": True})
    assert len(items_all) == 2
