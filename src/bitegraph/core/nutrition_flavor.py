"""Template-based nutrition and flavor enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import json

from bitegraph.core.models import (
    ClassificationResult,
    FoodVertical,
    MappingResult,
    NutritionFlavorResult,
    NutritionProfile,
    Provenance,
    PurchaseLineItem,
)

NUTRIENT_FIELDS = (
    "calories_kcal",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
)

FLAVOR_AXES = (
    "spicy",
    "sweet",
    "umami",
    "creamy",
    "fried",
    "acidic",
    "smoky",
    "fresh",
)


@dataclass(frozen=True)
class IngredientDefinition:
    ingredient_id: str
    serving_grams: float
    nutrients_per_100g: dict[str, float]
    flavor_profile: dict[str, float]


def _load_json_files(directory: Path | None, resource_dir: str) -> list[dict[str, Any]]:
    files: list[Path] = []
    data: list[dict[str, Any]] = []

    if directory:
        if not directory.exists():
            return []
        files = sorted(p for p in directory.iterdir() if p.suffix == ".json")
        for file_path in files:
            with file_path.open("r", encoding="utf-8") as handle:
                data.append(json.load(handle))
        return data

    try:
        resource_path = resources.files("bitegraph.templates").joinpath(resource_dir)
        for entry in resource_path.iterdir():
            if entry.name.endswith(".json"):
                with entry.open("r", encoding="utf-8") as handle:
                    data.append(json.load(handle))
    except FileNotFoundError:
        return []

    return data


class TemplateNutritionFlavorEnricher:
    """Enrich mapped events using ingredient templates with nutrient/flavor attributes."""

    def __init__(self, templates_path: str | Path | None = None) -> None:
        base_path = Path(templates_path) if templates_path else None
        self.ingredient_profiles = self._load_ingredient_profiles(base_path)
        self.ingredients = self._load_ingredients(base_path)

    def _load_ingredient_profiles(self, base_path: Path | None) -> dict[str, list[dict[str, Any]]]:
        profile_map: dict[str, list[dict[str, Any]]] = {}
        payloads = _load_json_files(
            base_path / "ingredient_profiles" if base_path else None,
            "ingredient_profiles",
        )
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            for profile in payload.get("ingredient_profiles", []) or []:
                profile_id = profile.get("ingredient_profile_id")
                ingredients = profile.get("ingredients") or []
                if profile_id and isinstance(ingredients, list):
                    profile_map[str(profile_id)] = [e for e in ingredients if isinstance(e, dict)]
        return profile_map

    def _load_ingredients(self, base_path: Path | None) -> dict[str, IngredientDefinition]:
        ingredient_map: dict[str, IngredientDefinition] = {}
        payloads = _load_json_files(base_path / "ingredients" if base_path else None, "ingredients")
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            for ingredient in payload.get("ingredients", []) or []:
                if not isinstance(ingredient, dict):
                    continue
                ingredient_id = ingredient.get("ingredient_id")
                if not ingredient_id:
                    continue
                nutrient_payload = ingredient.get("nutrients_per_100g") or {}
                flavor_payload = ingredient.get("flavor_profile") or {}
                nutrients = {key: float(nutrient_payload.get(key, 0.0)) for key in NUTRIENT_FIELDS}
                flavor_profile = {
                    axis: max(0.0, min(1.0, float(flavor_payload.get(axis, 0.0))))
                    for axis in FLAVOR_AXES
                }
                ingredient_map[str(ingredient_id)] = IngredientDefinition(
                    ingredient_id=str(ingredient_id),
                    serving_grams=float(ingredient.get("serving_grams", 100.0)),
                    nutrients_per_100g=nutrients,
                    flavor_profile=flavor_profile,
                )
        return ingredient_map

    def enrich(
        self,
        item: PurchaseLineItem,
        cls: ClassificationResult,
        mapping: MappingResult,
    ) -> NutritionFlavorResult | None:
        if cls.vertical != FoodVertical.FOOD:
            return None

        profile_id = mapping.ingredient_profile_id
        if not profile_id:
            return None

        profile_ingredients = self.ingredient_profiles.get(profile_id)
        if profile_ingredients is None:
            return NutritionFlavorResult(
                event_id=item.event_id,
                ingredient_profile_id=profile_id,
                nutrition=NutritionProfile(),
                flavor_axes={axis: 0.0 for axis in FLAVOR_AXES},
                ingredient_count=0,
                covered_ingredient_count=0,
                confidence=0.0,
                reasons=["ingredient_profile_missing"],
                provenance=Provenance.TEMPLATE_V1,
            )

        nutrition_totals = {key: 0.0 for key in NUTRIENT_FIELDS}
        flavor_totals = {axis: 0.0 for axis in FLAVOR_AXES}
        reasons: list[str] = []

        quantity_multiplier = max(item.quantity, 0.0)
        ingredient_count = len(profile_ingredients)
        covered = 0
        total_flavor_weight = 0.0

        for entry in profile_ingredients:
            ingredient_id = str(entry.get("ingredient_id", "")).strip()
            if not ingredient_id:
                continue

            amount_relative = max(0.0, float(entry.get("amount_relative", 0.0)))
            ingredient = self.ingredients.get(ingredient_id)
            if ingredient is None:
                reasons.append(f"unknown_ingredient:{ingredient_id}")
                continue

            covered += 1
            grams = ingredient.serving_grams * amount_relative * quantity_multiplier
            grams_factor = grams / 100.0
            for nutrient, value in ingredient.nutrients_per_100g.items():
                nutrition_totals[nutrient] += value * grams_factor

            total_flavor_weight += amount_relative
            for axis, value in ingredient.flavor_profile.items():
                flavor_totals[axis] += value * amount_relative

        if total_flavor_weight > 0:
            normalized_flavor = {
                axis: round(flavor_totals[axis] / total_flavor_weight, 4) for axis in FLAVOR_AXES
            }
        else:
            normalized_flavor = {axis: 0.0 for axis in FLAVOR_AXES}

        coverage = (covered / ingredient_count) if ingredient_count else 0.0
        confidence = round(max(0.0, min(1.0, mapping.confidence * coverage)), 4)

        nutrition = NutritionProfile(
            calories_kcal=round(nutrition_totals["calories_kcal"], 2),
            protein_g=round(nutrition_totals["protein_g"], 2),
            carbs_g=round(nutrition_totals["carbs_g"], 2),
            fat_g=round(nutrition_totals["fat_g"], 2),
            fiber_g=round(nutrition_totals["fiber_g"], 2),
            sugar_g=round(nutrition_totals["sugar_g"], 2),
            sodium_mg=round(nutrition_totals["sodium_mg"], 2),
        )

        if covered == 0:
            reasons.append("no_covered_ingredients")

        return NutritionFlavorResult(
            event_id=item.event_id,
            ingredient_profile_id=profile_id,
            nutrition=nutrition,
            flavor_axes=normalized_flavor,
            ingredient_count=ingredient_count,
            covered_ingredient_count=covered,
            confidence=confidence,
            reasons=reasons,
            provenance=Provenance.TEMPLATE_V1,
        )
