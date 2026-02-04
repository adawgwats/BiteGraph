"""Tests for rule-based classification."""

from datetime import datetime

from bitegraph.core.classify_rules import RuleBasedClassifier
from bitegraph.core.models import FoodKind, FoodVertical, PurchaseLineItem


def test_non_food_keyword() -> None:
    classifier = RuleBasedClassifier()
    item = PurchaseLineItem(
        event_id="evt1",
        source="uber_eats",
        merchant_name="Sample",
        timestamp=datetime.utcnow(),
        item_name_raw="Delivery Fee",
        modifiers_raw=None,
        quantity=1,
        unit_price=2.0,
        line_total=2.0,
        raw_ref="test",
        raw_payload_hash="hash",
    )
    result = classifier.classify(item)
    assert result.vertical == FoodVertical.NON_FOOD


def test_merchant_category() -> None:
    classifier = RuleBasedClassifier()
    item = PurchaseLineItem(
        event_id="evt2",
        source="uber_eats",
        merchant_name="Starbucks",
        timestamp=datetime.utcnow(),
        item_name_raw="Latte",
        modifiers_raw=None,
        quantity=1,
        unit_price=5.0,
        line_total=5.0,
        raw_ref="test",
        raw_payload_hash="hash",
    )
    result = classifier.classify(item)
    assert result.vertical == FoodVertical.FOOD
    assert result.food_kind == FoodKind.BEVERAGE


def test_unknown_item() -> None:
    classifier = RuleBasedClassifier()
    item = PurchaseLineItem(
        event_id="evt3",
        source="uber_eats",
        merchant_name="Unknown Place",
        timestamp=datetime.utcnow(),
        item_name_raw="Mystery Box",
        modifiers_raw=None,
        quantity=1,
        unit_price=10.0,
        line_total=10.0,
        raw_ref="test",
        raw_payload_hash="hash",
    )
    result = classifier.classify(item)
    assert result.vertical == FoodVertical.UNKNOWN
