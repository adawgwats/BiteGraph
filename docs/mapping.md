# Food Mapping & Canonicalization

## Overview

Mapping transforms raw item names into canonical food records with ingredient information. The goal is to enable pattern detection and swap recommendations.

Example: "Shroom Burger w/no pickles" -> canonical_food_id: "burger_mushroom_v1" -> ingredient_profile_id with {mushroom, beef patty, bun, special sauce}.

## Mapping Pipeline

```
PurchaseLineItem (item_name_raw: "Shroom Burger")
    -> Classifier (vertical: food, food_kind: prepared_meal)
    -> CanonicalFood lookup (templates)
    -> IngredientMapper
    -> MappingResult (canonical_food_id, ingredient_profile_id, confidence)
```

## Canonical Food Model

A canonical food is the "ground truth" record for a dish:

```json
{
  "canonical_food_id": "burger_mushroom_v1",
  "name": "Mushroom Burger",
  "aliases": ["Shroom Burger", "Mushroom Burger"],
  "food_kind": "prepared_meal",
  "default_ingredient_profile_id": "burger_mushroom_v1.base",
  "confidence": 0.95
}
```

Multiple ingredient profiles can exist for the same canonical food (variations).

## IngredientGraph

An ingredient graph maps a food to its components:

```python
IngredientGraph(
    ingredient_profile_id="burger_mushroom_v1.base",
    canonical_food_id="burger_mushroom_v1",
    ingredients=[
        {"ingredient_id": "beef_patty_4oz", "amount_relative": 1.0},
        {"ingredient_id": "mushroom_sauteed", "amount_relative": 0.5},
        {"ingredient_id": "bread_brioche_bun", "amount_relative": 1.0},
    ]
)
```


## Mapping Strategy (MVP)

### 1. Rule-Based Matching (JSON Templates)

Store known dishes in `templates/dishes/*.json`.

### 2. Modifier Rules

Modifier rules in `templates/modifiers/*.json` can adjust confidence or add mapping reasons (e.g., `extra`, `no`, `light`).

### 3. Confidence Scoring

```
confidence = base_confidence * (fuzzy_match / 100)
```

### 4. Fallback to Unknown

If no template matches with confidence > threshold, mark as unknown:

```python
MappingResult(
    event_id="...",
    canonical_food_id=None,
    ingredient_profile_id=None,
    confidence=0.2,
    reasons=["no_dish_match"]
)
```

## Nutrition + Flavor Enrichment (Template-First)

After `MappingResult` resolves an `ingredient_profile_id`, BiteGraph can compute a lightweight enrichment payload:

- Nutrition rollup: calories/protein/carbs/fat/fiber/sugar/sodium
- Flavor vector: spicy/sweet/umami/creamy/fried/acidic/smoky/fresh

This stage reuses local JSON templates (`templates/ingredient_profiles` + `templates/ingredients`) so it stays cheap and deterministic in local dev and on AWS.

## Grocery Mapping

- `grocery_raw`: map basic items (banana, chicken breast, rice) via a small dictionary file
- `grocery_packaged`: return a structured placeholder with low confidence

## Versioning & Evolution

When you update the mapping:
1. Increment the version number
2. Create new `FoodEventInterpretation` record
3. Store old versions for audit trail
4. Backfill historical events if desired

## Related Files

- `src/bitegraph/core/map_templates.py` - Mapping logic
- `src/bitegraph/templates/dishes/` - Canonical food definitions
- `docs/architecture.md` - Overview of pipeline stages
