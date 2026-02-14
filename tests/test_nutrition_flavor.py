"""Tests for nutrition/flavor enrichment."""

import json
from datetime import datetime
from pathlib import Path

from bitegraph.core.models import (
    ClassificationResult,
    FoodKind,
    FoodVertical,
    MappingResult,
    PurchaseLineItem,
)
from bitegraph.core.nutrition_flavor import TemplateNutritionFlavorEnricher


def _write_template(path: Path, relative_path: str, payload: dict) -> None:
    target = path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")


def _make_item(quantity: float = 1.0) -> PurchaseLineItem:
    return PurchaseLineItem(
        event_id="evt1",
        source="uber_eats",
        merchant_name="Sample Diner",
        timestamp=datetime.utcnow(),
        item_name_raw="Sample Item",
        modifiers_raw=None,
        quantity=quantity,
        unit_price=8.0,
        line_total=8.0 * quantity,
        raw_ref="test",
        raw_payload_hash="hash",
    )


def test_enrichment_rolls_up_nutrients_and_flavor(tmp_path: Path) -> None:
    _write_template(
        tmp_path,
        "ingredient_profiles/basic.json",
        {
            "ingredient_profiles": [
                {
                    "ingredient_profile_id": "sample_profile",
                    "canonical_food_id": "sample_food",
                    "ingredients": [
                        {"ingredient_id": "ing_a", "amount_relative": 1.0},
                        {"ingredient_id": "ing_b", "amount_relative": 0.5},
                    ],
                }
            ]
        },
    )
    _write_template(
        tmp_path,
        "ingredients/basic.json",
        {
            "ingredients": [
                {
                    "ingredient_id": "ing_a",
                    "serving_grams": 100.0,
                    "nutrients_per_100g": {
                        "calories_kcal": 100.0,
                        "protein_g": 10.0,
                        "carbs_g": 0.0,
                        "fat_g": 0.0,
                        "fiber_g": 0.0,
                        "sugar_g": 0.0,
                        "sodium_mg": 10.0,
                    },
                    "flavor_profile": {
                        "spicy": 0.0,
                        "sweet": 1.0,
                        "umami": 0.0,
                        "creamy": 0.0,
                        "fried": 0.0,
                        "acidic": 0.0,
                        "smoky": 0.0,
                        "fresh": 0.0,
                    },
                },
                {
                    "ingredient_id": "ing_b",
                    "serving_grams": 50.0,
                    "nutrients_per_100g": {
                        "calories_kcal": 200.0,
                        "protein_g": 20.0,
                        "carbs_g": 0.0,
                        "fat_g": 0.0,
                        "fiber_g": 0.0,
                        "sugar_g": 0.0,
                        "sodium_mg": 20.0,
                    },
                    "flavor_profile": {
                        "spicy": 0.0,
                        "sweet": 0.0,
                        "umami": 1.0,
                        "creamy": 0.0,
                        "fried": 0.0,
                        "acidic": 0.0,
                        "smoky": 0.0,
                        "fresh": 0.0,
                    },
                },
            ]
        },
    )

    enricher = TemplateNutritionFlavorEnricher(templates_path=tmp_path)
    item = _make_item(quantity=2.0)
    cls = ClassificationResult(
        event_id=item.event_id,
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.PREPARED_MEAL,
        confidence=0.9,
    )
    mapping = MappingResult(
        event_id=item.event_id,
        canonical_food_id="sample_food",
        ingredient_profile_id="sample_profile",
        confidence=0.9,
    )

    result = enricher.enrich(item, cls, mapping)

    assert result is not None
    assert result.nutrition.calories_kcal == 300.0
    assert result.nutrition.protein_g == 30.0
    assert result.flavor_axes["sweet"] == 0.6667
    assert result.flavor_axes["umami"] == 0.3333
    assert result.confidence == 0.9


def test_enrichment_tracks_unknown_ingredients(tmp_path: Path) -> None:
    _write_template(
        tmp_path,
        "ingredient_profiles/basic.json",
        {
            "ingredient_profiles": [
                {
                    "ingredient_profile_id": "sample_profile",
                    "canonical_food_id": "sample_food",
                    "ingredients": [
                        {"ingredient_id": "ing_a", "amount_relative": 1.0},
                        {"ingredient_id": "missing_ing", "amount_relative": 1.0},
                    ],
                }
            ]
        },
    )
    _write_template(
        tmp_path,
        "ingredients/basic.json",
        {
            "ingredients": [
                {
                    "ingredient_id": "ing_a",
                    "serving_grams": 100.0,
                    "nutrients_per_100g": {
                        "calories_kcal": 100.0,
                        "protein_g": 10.0,
                        "carbs_g": 0.0,
                        "fat_g": 0.0,
                        "fiber_g": 0.0,
                        "sugar_g": 0.0,
                        "sodium_mg": 10.0,
                    },
                    "flavor_profile": {
                        "spicy": 0.0,
                        "sweet": 0.0,
                        "umami": 0.0,
                        "creamy": 0.0,
                        "fried": 0.0,
                        "acidic": 0.0,
                        "smoky": 0.0,
                        "fresh": 0.0,
                    },
                }
            ]
        },
    )

    enricher = TemplateNutritionFlavorEnricher(templates_path=tmp_path)
    item = _make_item(quantity=1.0)
    cls = ClassificationResult(
        event_id=item.event_id,
        vertical=FoodVertical.FOOD,
        food_kind=FoodKind.PREPARED_MEAL,
        confidence=0.9,
    )
    mapping = MappingResult(
        event_id=item.event_id,
        canonical_food_id="sample_food",
        ingredient_profile_id="sample_profile",
        confidence=0.8,
    )

    result = enricher.enrich(item, cls, mapping)

    assert result is not None
    assert result.ingredient_count == 2
    assert result.covered_ingredient_count == 1
    assert result.confidence == 0.4
    assert "unknown_ingredient:missing_ing" in result.reasons
