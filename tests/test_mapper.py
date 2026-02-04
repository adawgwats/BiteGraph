"""Tests for template-based mapping."""

from datetime import datetime

from bitegraph.core.map_templates import TemplateIngredientMapper
from bitegraph.core.models import (
    ClassificationResult,
    FoodKind,
    FoodVertical,
    PurchaseLineItem,
)


def _make_item(name: str, modifiers: list[str] | None = None) -> PurchaseLineItem:
    return PurchaseLineItem(
        event_id="evt1",
        source="uber_eats",
        merchant_name="Sample Diner",
        timestamp=datetime.utcnow(),
        item_name_raw=name,
        modifiers_raw=modifiers,
        quantity=1,
        unit_price=9.0,
        line_total=9.0,
        raw_ref="test",
        raw_payload_hash="hash",
    )


def test_prepared_meal_mapping() -> None:
    mapper = TemplateIngredientMapper()
    item = _make_item("Shroom Burger")
    cls = ClassificationResult(
        event_id=item.event_id,
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.PREPARED_MEAL,
        confidence=0.8,
    )
    mapping = mapper.map(item, cls)
    assert mapping.canonical_food_id == "burger_mushroom_v1"
    assert mapping.ingredient_profile_id == "burger_mushroom_v1.base"
    assert mapping.confidence > 0.5


def test_modifier_boosts_confidence() -> None:
    mapper = TemplateIngredientMapper()
    item = _make_item("Shroom Burger", modifiers=["extra sauce"])
    cls = ClassificationResult(
        event_id=item.event_id,
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.PREPARED_MEAL,
        confidence=0.8,
    )
    mapping = mapper.map(item, cls)
    assert any("extra_modifier" in reason for reason in mapping.reasons)


def test_grocery_raw_mapping() -> None:
    mapper = TemplateIngredientMapper()
    item = _make_item("Fresh Banana")
    cls = ClassificationResult(
        event_id=item.event_id,
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.GROCERY_RAW,
        confidence=0.7,
    )
    mapping = mapper.map(item, cls)
    assert mapping.canonical_food_id == "banana_raw_v1"


def test_grocery_packaged_placeholder() -> None:
    mapper = TemplateIngredientMapper()
    item = _make_item("Granola Bar")
    cls = ClassificationResult(
        event_id=item.event_id,
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.GROCERY_PACKAGED,
        confidence=0.7,
    )
    mapping = mapper.map(item, cls)
    assert mapping.canonical_food_id == "unmapped_grocery_packaged"
