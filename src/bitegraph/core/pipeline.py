"""Pipeline orchestration: wires stages together with dependency injection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bitegraph.core.confidence import combine_confidences
from bitegraph.core.interfaces import (
    Adapter,
    Classifier,
    ConsumptionInferenceEngine,
    IngredientMapper,
    Normalizer,
    NutritionFlavorEnricher,
)
from bitegraph.core.models import (
    FoodVertical,
    ClassificationResult,
    ConsumptionInference,
    FoodEventInterpretation,
    MappingResult,
    NutritionFlavorResult,
    Provenance,
    PurchaseLineItem,
)


@dataclass
class PipelineResult:
    item: PurchaseLineItem
    interpretation: FoodEventInterpretation | None
    classification: ClassificationResult | None
    mapping: MappingResult | None
    enrichment: NutritionFlavorResult | None
    consumption: ConsumptionInference | None


class PipelineRunner:
    """
    Orchestrates the processing pipeline: adapt -> normalize -> classify -> map -> enrich -> infer.

    All stages are injected, so implementations can be swapped at runtime.
    """

    def __init__(
        self,
        adapters: list[Adapter] | None = None,
        normalizer: Optional[Normalizer] = None,
        classifier: Optional[Classifier] = None,
        mapper: Optional[IngredientMapper] = None,
        enricher: Optional[NutritionFlavorEnricher] = None,
        inference_engine: Optional[ConsumptionInferenceEngine] = None,
    ) -> None:
        self.adapters = adapters or []
        self.normalizer = normalizer
        self.classifier = classifier
        self.mapper = mapper
        self.enricher = enricher
        self.inference_engine = inference_engine

    def run(self, raw_items: list[PurchaseLineItem]) -> list[PipelineResult]:
        """Run the pipeline on a list of already-parsed items."""
        results: list[PipelineResult] = []
        for item in raw_items:
            normalized = self.normalizer.normalize(item) if self.normalizer else item
            classification = self.classifier.classify(normalized) if self.classifier else None
            mapping = (
                self.mapper.map(normalized, classification)
                if self.mapper and classification
                else None
            )
            enrichment = (
                self.enricher.enrich(normalized, classification, mapping)
                if self.enricher and classification and mapping
                else None
            )
            consumption = (
                self.inference_engine.infer(normalized, classification, mapping)
                if self.inference_engine and classification and mapping
                else None
            )
            interpretation = self._build_interpretation(normalized, classification, mapping)

            results.append(
                PipelineResult(
                    item=normalized,
                    interpretation=interpretation,
                    classification=classification,
                    mapping=mapping,
                    enrichment=enrichment,
                    consumption=consumption,
                )
            )
        return results

    def process_with_adapter(self, raw_bytes: bytes, metadata: dict) -> list[PipelineResult]:
        """Full pipeline: find adapter -> parse -> normalize -> classify -> map -> enrich -> infer."""
        adapter = next((a for a in self.adapters if a.can_parse(metadata)), None)
        if not adapter:
            raise ValueError(f"No adapter found for metadata: {metadata}")
        items = adapter.parse(raw_bytes, metadata)
        return self.run(items)

    def run_pipeline(self, raw_bytes: bytes, metadata: dict) -> list[PipelineResult]:
        """Stable integration entrypoint for external packages."""
        return self.process_with_adapter(raw_bytes, metadata)

    def _build_interpretation(
        self,
        item: PurchaseLineItem,
        classification: ClassificationResult | None,
        mapping: MappingResult | None,
    ) -> FoodEventInterpretation | None:
        if not classification and not mapping:
            return None

        confidence_values = []
        reasons: list[str] = []
        provenance = Provenance.RULES_V1

        if classification:
            confidence_values.append(classification.confidence)
            reasons.extend(classification.reasons)
        if mapping:
            confidence_values.append(mapping.confidence)
            reasons.extend(mapping.reasons)
            provenance = mapping.provenance

        confidence = combine_confidences(confidence_values, method="average")
        return FoodEventInterpretation(
            event_id=item.event_id,
            vertical=classification.vertical if classification else FoodVertical.UNKNOWN,
            food_kind=classification.food_kind if classification else None,
            canonical_food_id=mapping.canonical_food_id if mapping else None,
            ingredient_profile_id=mapping.ingredient_profile_id if mapping else None,
            confidence=confidence,
            provenance=provenance,
            reasons=reasons,
            version=1,
            updated_at=datetime.utcnow(),
        )
