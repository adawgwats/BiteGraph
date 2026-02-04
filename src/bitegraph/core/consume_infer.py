"""Consumption inference: determine if a purchase is likely to be consumed."""

from __future__ import annotations

from bitegraph.core.models import (
    ClassificationResult,
    ConsumptionInference,
    FoodKind,
    FoodVertical,
    MappingResult,
    PurchaseLineItem,
)


class DefaultConsumptionInference:
    """Default inference engine with simple heuristics."""

    def infer(
        self,
        item: PurchaseLineItem,
        cls: ClassificationResult,
        mapping: MappingResult | None = None,
    ) -> ConsumptionInference:
        if cls.vertical == FoodVertical.NON_FOOD:
            return ConsumptionInference(
                event_id=item.event_id,
                consumed_probability=0.0,
                reason_codes=["non_food"],
                version=1,
            )

        if cls.vertical == FoodVertical.UNKNOWN:
            return ConsumptionInference(
                event_id=item.event_id,
                consumed_probability=0.5,
                reason_codes=["unknown_vertical"],
                version=1,
            )

        if cls.food_kind == FoodKind.PREPARED_MEAL or cls.food_kind == FoodKind.BEVERAGE:
            return ConsumptionInference(
                event_id=item.event_id,
                consumed_probability=0.9,
                reason_codes=["restaurant_default"],
                version=1,
            )

        if cls.food_kind == FoodKind.GROCERY_PACKAGED:
            probability = 0.7
            reasons = ["grocery_packaged_default"]
            if item.quantity <= 1 and item.line_total <= 10:
                probability = 0.8
                reasons.append("grocery_single_serve")
            return ConsumptionInference(
                event_id=item.event_id,
                consumed_probability=probability,
                reason_codes=reasons,
                version=1,
            )

        if cls.food_kind == FoodKind.GROCERY_RAW:
            probability = 0.3
            reasons = ["grocery_raw_default"]
            if item.quantity <= 1:
                probability = 0.4
                reasons.append("grocery_small_batch")
            return ConsumptionInference(
                event_id=item.event_id,
                consumed_probability=probability,
                reason_codes=reasons,
                version=1,
            )

        return ConsumptionInference(
            event_id=item.event_id,
            consumed_probability=0.5,
            reason_codes=["unknown_food_kind"],
            version=1,
        )
