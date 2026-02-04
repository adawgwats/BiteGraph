"""Classification rules and logic for food vs. non-food determination."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import json
import yaml

from bitegraph.core.models import (
    ClassificationResult,
    FoodKind,
    FoodVertical,
    PurchaseLineItem,
)


@dataclass
class MerchantRule:
    raw_patterns: list[str]
    canonical: str | None = None
    category: str | None = None
    force_vertical: str | None = None
    force_food_kind: str | None = None


BEVERAGE_KEYWORDS = {
    "coffee",
    "latte",
    "espresso",
    "cappuccino",
    "tea",
    "soda",
    "cola",
    "smoothie",
    "juice",
    "milkshake",
    "shake",
    "frapp",
    "lemonade",
    "water",
}


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _load_yaml(path: Path | None, resource_name: str) -> dict[str, Any]:
    if path:
        file_path = path / resource_name
        if not file_path.exists():
            return {}
        with file_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    try:
        resource = resources.files("bitegraph.templates").joinpath(resource_name)
        with resource.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}


def _load_json_files(directory: Path | None, resource_dir: str) -> list[dict[str, Any]]:
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


class RuleBasedClassifier:
    """
    Deterministic rule-based classifier.

    Uses non_food_keywords.yaml and merchants.yaml for cheap-first classification.
    Optional heuristics can reduce unknowns when analyzing personal datasets.
    """

    def __init__(
        self,
        templates_path: str | Path | None = None,
        assume_food_if_priced: bool = False,
        default_food_kind: FoodKind | None = FoodKind.PREPARED_MEAL,
    ) -> None:
        self.templates_path = Path(templates_path) if templates_path else None
        self.non_food_keywords = self._load_non_food_keywords()
        self.merchant_rules = self._load_merchants()
        self.grocery_raw_keywords = self._load_grocery_raw_keywords()
        self.assume_food_if_priced = assume_food_if_priced
        self.default_food_kind = default_food_kind

    def _load_non_food_keywords(self) -> list[str]:
        data = _load_yaml(self.templates_path, "non_food_keywords.yaml")
        keywords = data.get("non_food_keywords", [])
        return [_normalize_text(k) for k in keywords if isinstance(k, str)]

    def _load_merchants(self) -> list[MerchantRule]:
        data = _load_yaml(self.templates_path, "merchants.yaml")
        rules: list[MerchantRule] = []
        for entry in data.get("merchants", []) or []:
            raw_patterns = entry.get("raw_patterns", []) or []
            if not raw_patterns:
                continue
            rules.append(
                MerchantRule(
                    raw_patterns=[str(p) for p in raw_patterns],
                    canonical=entry.get("canonical"),
                    category=entry.get("category"),
                    force_vertical=entry.get("force_vertical"),
                    force_food_kind=entry.get("force_food_kind"),
                )
            )
        return rules

    def _load_grocery_raw_keywords(self) -> list[str]:
        payloads = _load_json_files(self.templates_path / "dishes" if self.templates_path else None, "dishes")
        keywords: list[str] = []
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            raw_map = payload.get("grocery_raw")
            if isinstance(raw_map, dict):
                for key in raw_map.keys():
                    if key:
                        keywords.append(_normalize_text(str(key)))
        return keywords

    def classify(self, item: PurchaseLineItem) -> ClassificationResult:
        reasons: list[str] = []
        item_name = _normalize_text(item.item_name_raw or "")

        for keyword in self.non_food_keywords:
            if keyword and keyword in item_name:
                reasons.append(f"non_food_keyword:{keyword}")
                return ClassificationResult(
                    event_id=item.event_id,
                    vertical=FoodVertical.NON_FOOD,
                    food_kind=None,
                    confidence=0.95,
                    reasons=reasons,
                )

        if any(k in item_name for k in self.grocery_raw_keywords):
            matched = next(k for k in self.grocery_raw_keywords if k in item_name)
            reasons.append(f"grocery_raw_keyword:{matched}")
            return ClassificationResult(
                event_id=item.event_id,
                vertical=FoodVertical.FOOD,
                food_kind=FoodKind.GROCERY_RAW,
                confidence=0.75,
                reasons=reasons,
            )

        if any(k in item_name for k in BEVERAGE_KEYWORDS):
            reasons.append("beverage_keyword")
            return ClassificationResult(
                event_id=item.event_id,
                vertical=FoodVertical.FOOD,
                food_kind=FoodKind.BEVERAGE,
                confidence=0.7,
                reasons=reasons,
            )

        merchant_rule = self._match_merchant(item.merchant_name)
        if merchant_rule:
            forced = (merchant_rule.force_vertical or "").lower()
            if forced == "non_food":
                reasons.append("merchant_override:non_food")
                return ClassificationResult(
                    event_id=item.event_id,
                    vertical=FoodVertical.NON_FOOD,
                    food_kind=None,
                    confidence=0.9,
                    reasons=reasons,
                )
            if forced == "food":
                food_kind = self._category_to_food_kind(merchant_rule.category)
                reasons.append("merchant_override:food")
                return ClassificationResult(
                    event_id=item.event_id,
                    vertical=FoodVertical.FOOD,
                    food_kind=food_kind,
                    confidence=0.8,
                    reasons=reasons,
                )

            if merchant_rule.force_food_kind:
                food_kind = self._parse_food_kind(merchant_rule.force_food_kind)
                reasons.append("merchant_override:food_kind")
                return ClassificationResult(
                    event_id=item.event_id,
                    vertical=FoodVertical.FOOD,
                    food_kind=food_kind,
                    confidence=0.8,
                    reasons=reasons,
                )

            food_kind = self._category_to_food_kind(merchant_rule.category)
            if food_kind:
                reasons.append(f"merchant_category:{merchant_rule.category}")
                return ClassificationResult(
                    event_id=item.event_id,
                    vertical=FoodVertical.FOOD,
                    food_kind=food_kind,
                    confidence=0.7,
                    reasons=reasons,
                )

        if self.assume_food_if_priced and item.line_total > 0:
            reasons.append("assume_food_if_priced")
            return ClassificationResult(
                event_id=item.event_id,
                vertical=FoodVertical.FOOD,
                food_kind=self.default_food_kind,
                confidence=0.55,
                reasons=reasons,
            )

        reasons.append("no_rule_match")
        return ClassificationResult(
            event_id=item.event_id,
            vertical=FoodVertical.UNKNOWN,
            food_kind=None,
            confidence=0.4,
            reasons=reasons,
        )

    def _match_merchant(self, merchant_name: str) -> MerchantRule | None:
        if not merchant_name:
            return None
        merchant_norm = _normalize_text(merchant_name)
        for rule in self.merchant_rules:
            for pattern in rule.raw_patterns:
                if _normalize_text(pattern) in merchant_norm:
                    return rule
        return None

    def _category_to_food_kind(self, category: str | None) -> FoodKind | None:
        if not category:
            return None
        category = category.lower().strip()
        if category in {"beverage", "coffee", "tea"}:
            return FoodKind.BEVERAGE
        if category in {"grocery", "market"}:
            return FoodKind.GROCERY_PACKAGED
        if category in {"fast_food", "fast_casual", "restaurant"}:
            return FoodKind.PREPARED_MEAL
        return None

    def _parse_food_kind(self, value: str) -> FoodKind | None:
        value = value.lower().strip()
        for kind in FoodKind:
            if kind.value == value:
                return kind
        return None
