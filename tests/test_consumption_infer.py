"""Tests for consumption inference."""

from datetime import datetime

from bitegraph.core.consume_infer import DefaultConsumptionInference
from bitegraph.core.models import ClassificationResult, FoodKind, FoodVertical, PurchaseLineItem


def _item() -> PurchaseLineItem:
    return PurchaseLineItem(
        event_id="evt1",
        source="uber_eats",
        merchant_name="Sample",
        timestamp=datetime.utcnow(),
        item_name_raw="Burger",
        modifiers_raw=None,
        quantity=1,
        unit_price=9.0,
        line_total=9.0,
        raw_ref="test",
        raw_payload_hash="hash",
    )


def test_non_food_probability_zero() -> None:
    engine = DefaultConsumptionInference()
    cls = ClassificationResult(event_id="evt1", vertical=FoodVertical.NON_FOOD, confidence=0.9)
    inference = engine.infer(_item(), cls, None)
    assert inference.consumed_probability == 0.0


def test_prepared_meal_probability() -> None:
    engine = DefaultConsumptionInference()
    cls = ClassificationResult(
        event_id="evt1",
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.PREPARED_MEAL,
        confidence=0.9,
    )
    inference = engine.infer(_item(), cls, None)
    assert inference.consumed_probability == 0.9


def test_grocery_packaged_probability_range() -> None:
    engine = DefaultConsumptionInference()
    cls = ClassificationResult(
        event_id="evt1",
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.GROCERY_PACKAGED,
        confidence=0.7,
    )
    inference = engine.infer(_item(), cls, None)
    assert 0.6 <= inference.consumed_probability <= 0.8
