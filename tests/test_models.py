"""Tests for core data models."""

import pytest
from datetime import datetime
from bitegraph.core.models import (
    PurchaseLineItem,
    FoodEventInterpretation,
    IngredientGraph,
    FoodVertical,
    FoodKind,
    Provenance,
)


def test_purchase_line_item_immutable():
    """Test that PurchaseLineItem is frozen."""
    item = PurchaseLineItem(
        event_id="test123",
        user_id="user1",
        source="uber_eats",
        merchant_name="Shake Shack",
        timestamp=datetime.now(),
        item_name_raw="Burger",
        modifiers_raw=["no pickles"],
        quantity=1.0,
        unit_price=10.0,
        line_total=10.0,
        raw_ref="order_123",
        raw_payload_hash="abc123",
    )

    # Attempting to modify should raise an error
    with pytest.raises(Exception):  # FrozenInstanceError
        item.item_name_raw = "Changed"


def test_food_event_interpretation_versioned():
    """Test FoodEventInterpretation versioning."""
    interp_v1 = FoodEventInterpretation(
        event_id="test123",
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.PREPARED_MEAL,
        canonical_food_id="burger_classic_v1",
        confidence=0.95,
        version=1,
        updated_at=datetime.now(),
    )

    assert interp_v1.version == 1
    assert interp_v1.vertical == FoodVertical.FOOD

    # Can create a new version
    interp_v2 = FoodEventInterpretation(
        event_id="test123",
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.PREPARED_MEAL,
        canonical_food_id="burger_mushroom_v1",  # Changed
        confidence=0.98,
        version=2,
        updated_at=datetime.now(),
        provenance=Provenance.USER_OVERRIDE,
    )

    assert interp_v2.version == 2
    assert interp_v2.canonical_food_id != interp_v1.canonical_food_id


def test_ingredient_graph_immutable():
    """Test that IngredientGraph is frozen."""
    graph = IngredientGraph(
        ingredient_profile_id="burger_v1.base",
        canonical_food_id="burger_classic_v1",
        ingredients=[
            {"ingredient_id": "beef_patty", "amount_relative": 1.0},
            {"ingredient_id": "bun", "amount_relative": 1.0},
        ],
        version=1,
    )

    with pytest.raises(Exception):  # FrozenInstanceError
        graph.ingredients = []


def test_vertical_enum():
    """Test FoodVertical enum values."""
    assert FoodVertical.FOOD.value == "food"
    assert FoodVertical.NON_FOOD.value == "non_food"
    assert FoodVertical.UNKNOWN.value == "unknown"


def test_food_kind_enum():
    """Test FoodKind enum values."""
    kinds = [
        (FoodKind.PREPARED_MEAL, "prepared_meal"),
        (FoodKind.GROCERY_PACKAGED, "grocery_packaged"),
        (FoodKind.GROCERY_RAW, "grocery_raw"),
        (FoodKind.BEVERAGE, "beverage"),
    ]
    for kind, value in kinds:
        assert kind.value == value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
