"""Template-based ingredient mapping and canonical food lookup."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import json
from rapidfuzz import fuzz

from bitegraph.core.models import (
    ClassificationResult,
    FoodKind,
    FoodVertical,
    MappingResult,
    Provenance,
    PurchaseLineItem,
)


@dataclass
class DishTemplate:
    canonical_food_id: str
    name: str
    aliases: list[str]
    food_kind: str | None
    default_ingredient_profile_id: str | None
    confidence: float


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
            if entry.suffix == ".json":
                with entry.open("r", encoding="utf-8") as handle:
                    data.append(json.load(handle))
    except FileNotFoundError:
        return []

    return data


class TemplateIngredientMapper:
    """
    Template-driven mapper using dish aliases and modifier rules.

    - Prepared meals: fuzzy match item_name_raw against aliases.
    - Grocery raw: map simple items via a small dictionary file.
    - Grocery packaged: return a structured placeholder with low confidence.
    """

    def __init__(self, templates_path: str | Path | None = None, match_threshold: int = 85) -> None:
        base_path = Path(templates_path) if templates_path else None
        self.match_threshold = match_threshold
        self.dishes = self._load_dish_templates(base_path)
        self.modifier_rules = self._load_modifier_rules(base_path)
        self.grocery_raw_map = self._load_grocery_raw_map(base_path)

    def _load_dish_templates(self, base_path: Path | None) -> list[DishTemplate]:
        dishes: list[DishTemplate] = []
        payloads = _load_json_files(base_path / "dishes" if base_path else None, "dishes")
        for payload in payloads:
            entries = []
            if isinstance(payload, dict):
                entries = payload.get("canonical_foods", []) or []
            elif isinstance(payload, list):
                entries = payload
            for entry in entries:
                canonical_food_id = entry.get("canonical_food_id")
                name = entry.get("name")
                if not canonical_food_id or not name:
                    continue
                aliases = entry.get("aliases", []) or []
                aliases = [name] + [a for a in aliases if a and a != name]
                dishes.append(
                    DishTemplate(
                        canonical_food_id=canonical_food_id,
                        name=name,
                        aliases=aliases,
                        food_kind=entry.get("food_kind"),
                        default_ingredient_profile_id=entry.get("default_ingredient_profile_id"),
                        confidence=float(entry.get("confidence", 0.7)),
                    )
                )
        return dishes

    def _load_modifier_rules(self, base_path: Path | None) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        payloads = _load_json_files(base_path / "modifiers" if base_path else None, "modifiers")
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            for rule in payload.get("modifier_rules", []) or []:
                if rule.get("pattern"):
                    rules.append(rule)
        return rules

    def _load_grocery_raw_map(self, base_path: Path | None) -> dict[str, str]:
        payloads = _load_json_files(base_path / "dishes" if base_path else None, "dishes")
        grocery_map: dict[str, str] = {}
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            raw_map = payload.get("grocery_raw")
            if isinstance(raw_map, dict):
                for key, value in raw_map.items():
                    if key and value:
                        grocery_map[key.lower().strip()] = str(value)
        return grocery_map

    def map(self, item: PurchaseLineItem, cls: ClassificationResult) -> MappingResult:
        reasons: list[str] = []

        if cls.vertical != FoodVertical.FOOD:
            return MappingResult(
                event_id=item.event_id,
                canonical_food_id=None,
                ingredient_profile_id=None,
                confidence=0.0,
                reasons=["not_food"],
                provenance=Provenance.TEMPLATE_V1,
            )

        if cls.food_kind == FoodKind.GROCERY_RAW:
            return self._map_grocery_raw(item)

        if cls.food_kind == FoodKind.GROCERY_PACKAGED:
            return MappingResult(
                event_id=item.event_id,
                canonical_food_id="unmapped_grocery_packaged",
                ingredient_profile_id=None,
                confidence=0.2,
                reasons=["packaged_grocery_unmapped"],
                provenance=Provenance.TEMPLATE_V1,
            )

        best_match = self._best_dish_match(item.item_name_raw)
        if not best_match:
            return MappingResult(
                event_id=item.event_id,
                canonical_food_id=None,
                ingredient_profile_id=None,
                confidence=0.1,
                reasons=["no_dish_match"],
                provenance=Provenance.TEMPLATE_V1,
            )

        dish, alias, score = best_match
        confidence = dish.confidence * (score / 100)
        reasons.append(f"dish_match:{alias}")

        confidence = self._apply_modifier_rules(item, confidence, reasons)
        confidence = max(0.0, min(1.0, confidence))

        return MappingResult(
            event_id=item.event_id,
            canonical_food_id=dish.canonical_food_id,
            ingredient_profile_id=dish.default_ingredient_profile_id,
            confidence=confidence,
            reasons=reasons,
            provenance=Provenance.TEMPLATE_V1,
        )

    def _best_dish_match(self, item_name: str) -> tuple[DishTemplate, str, float] | None:
        if not item_name:
            return None
        best: tuple[DishTemplate, str, float] | None = None
        for dish in self.dishes:
            for alias in dish.aliases:
                score = fuzz.WRatio(item_name, alias)
                if best is None or score > best[2]:
                    best = (dish, alias, score)
        if best and best[2] >= self.match_threshold:
            return best
        return None

    def _apply_modifier_rules(
        self, item: PurchaseLineItem, confidence: float, reasons: list[str]
    ) -> float:
        if not item.modifiers_raw:
            return confidence
        updated = confidence
        for modifier in item.modifiers_raw:
            for rule in self.modifier_rules:
                pattern = str(rule.get("pattern", ""))
                if not pattern:
                    continue
                text = modifier or ""
                if rule.get("case_insensitive", True):
                    match = pattern.lower() in text.lower()
                else:
                    match = pattern in text
                if match:
                    boost = float(rule.get("confidence_boost", 0.0))
                    updated = max(0.0, min(1.0, updated + boost))
                    reason = rule.get("reason")
                    if reason:
                        reasons.append(str(reason))
        return updated

    def _map_grocery_raw(self, item: PurchaseLineItem) -> MappingResult:
        item_lower = (item.item_name_raw or "").lower()
        best_key = None
        for key in self.grocery_raw_map.keys():
            if key in item_lower:
                if best_key is None or len(key) > len(best_key):
                    best_key = key
        if best_key:
            canonical_id = self.grocery_raw_map[best_key]
            return MappingResult(
                event_id=item.event_id,
                canonical_food_id=canonical_id,
                ingredient_profile_id=f"{canonical_id}.base",
                confidence=0.7,
                reasons=[f"grocery_raw_match:{best_key}"],
                provenance=Provenance.TEMPLATE_V1,
            )

        return MappingResult(
            event_id=item.event_id,
            canonical_food_id=None,
            ingredient_profile_id=None,
            confidence=0.2,
            reasons=["grocery_raw_unmapped"],
            provenance=Provenance.TEMPLATE_V1,
        )
