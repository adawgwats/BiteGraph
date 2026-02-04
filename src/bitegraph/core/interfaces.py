"""Protocol definitions for BiteGraph adapters and stages."""

from typing import Any, Protocol, runtime_checkable

from bitegraph.core.models import (
    ClassificationResult,
    ConsumptionInference,
    MappingResult,
    PurchaseLineItem,
)


@runtime_checkable
class Adapter(Protocol):
    """
    Adapter protocol: converts raw data from a source into PurchaseLineItem events.

    Each adapter is responsible for:
    - Identifying whether it can parse given data
    - Extracting structure from the raw format
    - Normalizing into immutable PurchaseLineItem records
    """

    def source_id(self) -> str:
        """
        Return a unique identifier for this adapter's source.

        Examples: 'uber_eats', 'doordash', 'csv_import'
        """
        ...

    def can_parse(self, metadata: dict[str, Any]) -> bool:
        """
        Determine if this adapter can parse data with the given metadata.

        Args:
            metadata: Context about the raw data (e.g., {'format': 'json', 'source': 'uber_eats'})

        Returns:
            True if this adapter recognizes the format, False otherwise.
        """
        ...

    def parse(self, raw_bytes: bytes, metadata: dict[str, Any]) -> list[PurchaseLineItem]:
        """
        Parse raw data and emit PurchaseLineItem records.

        Args:
            raw_bytes: Raw bytes from the source
            metadata: Context (e.g., user_id, timestamp, file path)

        Returns:
            List of normalized PurchaseLineItem records

        Raises:
            ValueError: If parsing fails
        """
        ...


@runtime_checkable
class Normalizer(Protocol):
    """Normalizer protocol: clean and standardize fields in a PurchaseLineItem."""

    def normalize(self, item: PurchaseLineItem) -> PurchaseLineItem:
        """
        Return a cleaned version of the item (e.g., trimmed, lowercased merchant name).

        Args:
            item: Raw PurchaseLineItem

        Returns:
            Normalized PurchaseLineItem with consistent field formatting
        """
        ...


@runtime_checkable
class Classifier(Protocol):
    """Classifier protocol: determine if an item is food/non-food and its subtype."""

    def classify(self, item: PurchaseLineItem) -> ClassificationResult:
        """
        Classify the item into food/non_food/unknown and optionally a subtype.

        Args:
            item: PurchaseLineItem to classify

        Returns:
            ClassificationResult with vertical, food_kind, confidence, and reasons
        """
        ...


@runtime_checkable
class IngredientMapper(Protocol):
    """IngredientMapper protocol: link raw items to canonical foods and ingredients."""

    def map(self, item: PurchaseLineItem, cls: ClassificationResult) -> MappingResult:
        """
        Map a classified item to a canonical food and ingredient profile.

        Args:
            item: The PurchaseLineItem
            cls: Its ClassificationResult

        Returns:
            MappingResult with canonical_food_id, ingredient_profile_id, and confidence
        """
        ...


@runtime_checkable
class ConsumptionInferenceEngine(Protocol):
    """ConsumptionInferenceEngine protocol: infer whether a purchase will be consumed."""

    def infer(
        self,
        item: PurchaseLineItem,
        cls: ClassificationResult,
        mapping: MappingResult,
    ) -> ConsumptionInference:
        """
        Infer whether this item will be consumed (vs. stored/wasted).

        Args:
            item: The PurchaseLineItem
            cls: Its ClassificationResult
            mapping: Its MappingResult

        Returns:
            ConsumptionInference with consumed_probability and reason_codes
        """
        ...
