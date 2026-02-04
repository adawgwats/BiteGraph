"""BiteGraph: Modular food event normalization and enrichment engine."""

__version__ = "0.1.0"

# Core exports
from bitegraph.core.models import (
    PurchaseLineItem,
    FoodEventInterpretation,
    IngredientGraph,
    ClassificationResult,
    MappingResult,
    ConsumptionInference,
)
from bitegraph.core.interfaces import (
    Adapter,
    Normalizer,
    Classifier,
    IngredientMapper,
    ConsumptionInferenceEngine,
)
from bitegraph.core.pipeline import PipelineRunner, PipelineResult
from bitegraph.core.registry import AdapterRegistry
from bitegraph.core.classify_rules import RuleBasedClassifier
from bitegraph.core.map_templates import TemplateIngredientMapper
from bitegraph.core.consume_infer import DefaultConsumptionInference

__all__ = [
    "PurchaseLineItem",
    "FoodEventInterpretation",
    "IngredientGraph",
    "ClassificationResult",
    "MappingResult",
    "ConsumptionInference",
    "Adapter",
    "Normalizer",
    "Classifier",
    "IngredientMapper",
    "ConsumptionInferenceEngine",
    "PipelineRunner",
    "PipelineResult",
    "AdapterRegistry",
    "RuleBasedClassifier",
    "TemplateIngredientMapper",
    "DefaultConsumptionInference",
]
