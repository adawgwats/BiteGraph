# BiteGraph Architecture

## Overview

BiteGraph is a modular, pluggable food event normalization engine. It converts messy, real-world order data into structured, typed events that can feed downstream analytics and insights.

## Core Design Principles

1. **Adapter-first**: Each data source (Uber Eats, DoorDash, CSV export, email, etc.) is a plugin. Core has no source-specific logic.
2. **Immutability + versioned overlays**: Raw PurchaseLineItem records are frozen; interpretations (classifications, mappings) are versioned, auditable, and updatable.
3. **Composition over inheritance**: Stages are protocols/interfaces, not base classes. This allows swapping implementations without modifying core.
4. **Separation of policy from mechanism**: Business rules live in YAML/JSON templates; code is general.

## Pipeline Stages

```
raw data -> Adapter -> PurchaseLineItem
        -> Normalizer -> normalized PurchaseLineItem
        -> Classifier -> ClassificationResult (vertical, food_kind, confidence)
        -> Mapper -> MappingResult (canonical_food_id, ingredient_profile_id)
        -> ConsumptionInferenceEngine -> ConsumptionInference (consumed_probability)
```

### 1. Adapter (Source-Specific)

**Input**: Raw bytes (CSV, JSON, HTML, email, PDF, etc.)
**Output**: `PurchaseLineItem` records

Each adapter:
- Identifies whether it can parse the data (`can_parse()`)
- Extracts structure (merchant, items, timestamp, order_id, price, modifiers)
- Computes stable `event_id` hashes for deduplication
- Stores reference to raw source (`raw_ref`) and payload hash

### 2. Normalizer (Optional)

Cleans up fields:
- Merchant name: trim, lowercase, deduplicate variations ("SBUX" -> "Starbucks")
- Item names: remove extra whitespace, normalize capitalization
- Modifiers: standardize format

### 3. Classifier

Uses cheap-first rules (non-food keywords, merchant overrides) to determine:
- Is this a food item or non-food?
- If food: what subtype? (prepared meal, packaged grocery, raw grocery, beverage)

### 4. Mapper (IngredientMapper)

Links raw items to canonical foods:
- "Shroom Burger" -> canonical_food_id: "burger_mushroom_v1"
- Links to versioned ingredient graph

### 5. ConsumptionInferenceEngine

Answers: "Will this item be eaten soon after purchase?"

## Stable `event_id` Formula

Adapters must compute a deterministic event_id hash using:

```
source + merchant + timestamp + item_name_raw + modifiers_raw + line_total (+ order_id if present)
```

This ensures idempotency across reprocessing.

## Data Model

### Immutable: PurchaseLineItem

```python
@dataclass(frozen=True)
class PurchaseLineItem:
    event_id: str                      # Stable hash
    user_id: str | None
    source: str                        # "uber_eats", "doordash", etc.
    merchant_name: str
    timestamp: datetime | None
    item_name_raw: str
    modifiers_raw: list[str] | None
    quantity: float
    unit_price: float
    line_total: float
    raw_ref: str                       # Path/ID of source
    raw_payload_hash: str              # For idempotency
```

### Versioned: FoodEventInterpretation

```python
@dataclass
class FoodEventInterpretation:
    event_id: str                      # FK to PurchaseLineItem.event_id
    vertical: FoodVertical
    food_kind: FoodKind | None
    canonical_food_id: str | None
    ingredient_profile_id: str | None
    portion_multiplier: float
    confidence: float                  # 0-1
    provenance: Provenance             # "rules_v1", "template_v1", "user_override"
    reasons: list[str]
    version: int
    updated_at: datetime
```

### Immutable: IngredientGraph

```python
@dataclass(frozen=True)
class IngredientGraph:
    ingredient_profile_id: str
    canonical_food_id: str
    ingredients: list[dict]             # [{"ingredient_id": "...", "amount_relative": 0.5}]
    version: int
    source: str                         # "template", "user_curated", "llm_inferred"
    created_at: datetime
```

### Consumption Inference

```python
@dataclass
class ConsumptionInference:
    event_id: str
    consumed_probability: float
    reason_codes: list[str]
    version: int
```

## Integration Contract (Private AWS Package)

BiteGraph exposes a stable entrypoint so private infrastructure can call it without importing AWS code.

### Entrypoint

```
run_pipeline(raw_bytes, metadata) -> list[PipelineResult]
```

### Metadata Format

```
{
  "source": "uber_eats",
  "user_id": "user123",
  "file_path": "/path/to/export.csv",
  "raw_ref": "s3://bucket/key.csv"    # optional
}
```

### JSONL Output Schema

- **normalized.jsonl**: one `PurchaseLineItem` per line
- **interpreted.jsonl**: `{ item, classification, interpretation }`
- **mapped.jsonl**: `{ item, classification, mapping, consumption, interpretation }`

## Extensibility

### Adding a New Adapter

1. Implement `Adapter` protocol (3 methods)
2. Add synthetic fixtures
3. Register in `AdapterRegistry`
4. No changes to core

### Updating Food Knowledge

1. Edit YAML/JSON templates
2. Increment version
3. Re-run pipeline (idempotent via `event_id` + `raw_payload_hash`)
4. New interpretations created; old ones preserved in history

## Privacy & Auditing

- Raw source data is encrypted at rest and can be deleted after interpretation
- All interpretations are versioned and timestamped
- Provenance tracks how decisions were made
- Reasons explain each classification for transparency
