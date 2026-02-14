# Building Adapters for BiteGraph

## Overview

An adapter is a plugin that parses raw data from a specific source and emits `PurchaseLineItem` records. Each adapter handles the unique format and quirks of its source (Uber Eats CSV, email exports, PDFs, etc.).

## The Adapter Protocol

```python
@runtime_checkable
class Adapter(Protocol):
    def source_id(self) -> str:
        ...
    def can_parse(self, metadata: dict[str, Any]) -> bool:
        ...
    def parse(self, raw_bytes: bytes, metadata: dict[str, Any]) -> list[PurchaseLineItem]:
        ...
```

## Email Adapters (Generic Receipts)

For email receipts, prefer one adapter (`email_generic`) that dispatches to
sub-parsers in priority order. This keeps onboarding minimal and avoids
per-merchant setup.

Suggested dispatch order:
1. Known sender templates (high confidence)
2. HTML structured markup (schema.org Order/Invoice)
3. Attachments (PDF/CSV/HTML)
4. Plain-text heuristics (low confidence)

See `docs/email_ingestion.md` for details and a recommended extraction schema.

## Step-by-Step: Creating a New Adapter

### 1. Copy the Template

```
cp -r src/bitegraph/adapters/_template_adapter src/bitegraph/adapters/my_source
```

### 2. Implement `adapter.py`

Parse your source format and emit `PurchaseLineItem` items.

### 3. Create Synthetic Fixtures

Add files to `fixtures/` (CSV, JSON, or other format):

Rules:
- Synthetic (fake) data only
- Realistic structure and values
- No real merchant names, addresses, emails, or payment data

### 4. Document in `README.md`

Describe:
- Input format and sample
- Column mapping
- Known quirks

### 5. Register the Adapter

If you are wiring adapters centrally, register the adapter in `AdapterRegistry`.

### 6. Add Tests

Include tests for:
- Basic parsing
- Edge cases (missing columns, empty orders)
- Error handling (malformed data)
- Idempotency (same input -> same event_id)

## Stable event_id

Use a deterministic hash of:

```
source + merchant + timestamp + item_name_raw + modifiers_raw + line_total (+ order_id if present)
```

This ensures the same item always gets the same ID, enabling deduplication and idempotency.

## Error Handling

Raise `ValueError` with clear messages when parsing fails.

## Testing Your Adapter

```bash
pytest tests/test_ubereats_adapter.py -v
```

## Questions?

See `docs/architecture.md` for design rationale, or `CONTRIBUTING.md` for workflow.
