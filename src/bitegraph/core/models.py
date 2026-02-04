"""Core immutable data models and versioned overlays."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class FoodVertical(str, Enum):
    """Top-level classification: food, non-food, or unknown."""

    FOOD = "food"
    NON_FOOD = "non_food"
    UNKNOWN = "unknown"


class FoodKind(str, Enum):
    """Subtype for food items."""

    PREPARED_MEAL = "prepared_meal"
    GROCERY_PACKAGED = "grocery_packaged"
    GROCERY_RAW = "grocery_raw"
    BEVERAGE = "beverage"


class Provenance(str, Enum):
    """Source of interpretation/mapping."""

    RULES_V1 = "rules_v1"
    TEMPLATE_V1 = "template_v1"
    USER_OVERRIDE = "user_override"
    LLM_INFERRED = "llm_inferred"


@dataclass(frozen=True)
class PurchaseLineItem:
    """
    Immutable normalized purchase line item.

    This is the canonical event emitted by adapters and the pipeline.
    All fields are stable and never change; interpretations are versioned overlays.
    """

    event_id: str
    """Stable hash of source + merchant + timestamp + item_name_raw + modifiers_raw + line_total (+ order_id if present)."""

    user_id: Optional[str] = None
    """User identifier. Optional for OSS demo."""

    source: str = ""
    """Source system (e.g., 'uber_eats', 'doordash', 'csv_import')."""

    merchant_name: str = ""
    """Normalized merchant/restaurant name."""

    timestamp: Optional[datetime] = None
    """Order/transaction timestamp."""

    item_name_raw: str = ""
    """Raw item name as received from source."""

    modifiers_raw: Optional[list[str]] = None
    """Raw modifiers (size, toppings, etc.)."""

    quantity: float = 1.0
    """Item quantity."""

    unit_price: float = 0.0
    """Price per unit."""

    line_total: float = 0.0
    """Total for this line (quantity * unit_price or as-given)."""

    raw_ref: str = ""
    """Reference to raw source (file path, S3 key, email ID)."""

    raw_payload_hash: str = ""
    """SHA256 hash of raw payload for idempotency."""


@dataclass
class FoodEventInterpretation:
    """
    Versioned interpretation overlay for a PurchaseLineItem.

    This record is mutable and evolves as mappings improve.
    Always include version and updated_at for auditing.
    """

    event_id: str
    """Foreign key to PurchaseLineItem.event_id."""

    vertical: FoodVertical
    """Top-level classification: food, non_food, unknown."""

    food_kind: Optional[FoodKind] = None
    """Subtype if vertical=FOOD."""

    canonical_food_id: Optional[str] = None
    """Reference to canonical food record (e.g., 'burger_beef_classic_v1')."""

    ingredient_profile_id: Optional[str] = None
    """Reference to versioned ingredient graph."""

    portion_multiplier: float = 1.0
    """Adjustment for actual portion (e.g., 0.5 for half, 2.0 for double)."""

    confidence: float = 0.0
    """Confidence score 0-1."""

    provenance: Provenance = Provenance.RULES_V1
    """How this interpretation was determined."""

    reasons: list[str] = field(default_factory=list)
    """Explanation of classification decision."""

    version: int = 1
    """Schema version for this interpretation."""

    updated_at: Optional[datetime] = None
    """When this interpretation was last updated."""


@dataclass(frozen=True)
class IngredientGraph:
    """
    Versioned ingredient composition for a food item.

    Links a canonical_food_id to its components with amounts.
    """

    ingredient_profile_id: str
    """Unique identifier for this ingredient composition."""

    canonical_food_id: str
    """Which food item this describes."""

    ingredients: list[dict] = field(default_factory=list)
    """
    List of {"ingredient_id": str, "amount_relative": float, "notes": str | None}
    amount_relative is unitless (0-1 scale, or can be relative to base).
    """

    version: int = 1
    """Version of this ingredient graph."""

    source: str = ""
    """How this was generated (template, user_curated, llm_inferred)."""

    created_at: Optional[datetime] = None
    """When this graph was created."""


@dataclass
class ClassificationResult:
    """Output of the Classifier stage."""

    event_id: str
    vertical: FoodVertical
    food_kind: Optional[FoodKind] = None
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class MappingResult:
    """Output of the IngredientMapper stage."""

    event_id: str
    canonical_food_id: Optional[str] = None
    ingredient_profile_id: Optional[str] = None
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    provenance: Provenance = Provenance.TEMPLATE_V1


@dataclass
class ConsumptionInference:
    """Output of the ConsumptionInferenceEngine stage."""

    event_id: str
    consumed_probability: float
    """Probability this purchase will be consumed (0-1)."""

    reason_codes: list[str] = field(default_factory=list)
    """Reason codes (e.g., 'restaurant_default', 'grocery_bulk_default')."""

    version: int = 1
    """Version of the inference model."""
