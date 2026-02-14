# Generic Email Purchase Ingestion

## Goal

Enable automatic ingestion of purchase data from email receipts without per-merchant onboarding. Email is the universal inbox across mobile platforms, so users only connect/forward once.

## System Boundary

BiteGraph handles parsing and normalization. Email retrieval, encryption-at-rest, and account linking live upstream.

```
Email inbox -> Ingestion service -> raw email stored (encrypted)
            -> BiteGraph Email Adapter -> PurchaseLineItem
            -> Classify / Map / Infer -> FoodEvent projections
```

## Ingestion Paths (User Onboarding)

1. **Inbound alias (preferred)**: `receipts+<user_id>@inbound.<domain>`
   - Users set a single mailbox rule to forward receipts.
2. **OAuth mailbox connect (optional)**:
   - Gmail/Outlook connectors fetch receipt-like messages automatically.
3. **Share/forward fallback**:
   - User forwards a single receipt from any mobile app when needed.

No per-merchant setup is required.

## Email Adapter Design

Create one adapter: `email_generic`. It routes to sub-parsers in priority order.

### Parsing Tiers

1. **Known sender templates**
   - Match sender domain + subject patterns.
   - Use strict parsers for high confidence.
2. **Structured markup**
   - Parse schema.org `Order` / `Invoice` JSON-LD in HTML.
3. **Attachment parsing**
   - Extract from attached PDF/CSV/HTML (if present).
4. **Text heuristic fallback**
   - Extract line items and totals from plain text.
   - Output low confidence if ambiguous.

### Standard Extraction Schema

Each parser should attempt to extract:

- merchant / store name
- order timestamp
- line items + modifiers
- totals (optional)
- order_id (for dedupe)
- currency (optional)

### Dedupe Strategy

Use layered idempotency:

1. `message_id` / `raw_payload_hash`
2. `order_id` (if present)
3. Stable `event_id` hash per line item

## Avoiding Manual Item Onboarding

Use the CanonicalFood mapping system as the default onboarding mechanism:

- Maintain alias lists and fuzzy matching across merchants.
- Track merchant-specific aliases (menu names) that map to canonical foods.
- Promote frequent unknowns into alias tables automatically.
- Low confidence items are still ingested; users can optionally correct later.

This preserves the "store raw forever, mappings improve over time" rule.

## Confidence + Review Loop

Emit confidence and reasons at every stage:

- If parse confidence is below threshold, still emit `ORDER_INGESTED`
  but mark items as `unknown` with explicit reasons.
- Optional review queue: users only see low-confidence items, not every order.

## FoodEvent Projection (FlavCliq)

Map BiteGraph outputs into FoodEvents:

- `ORDER_INGESTED`: raw email + parsed metadata
- `MEAL_ITEM`: one per PurchaseLineItem
- `MEAL_OCCASION`: derived grouping (lunch/dinner/snack)

This keeps the FoodEvent-first model while reusing BiteGraph normalization.

## Privacy

- Raw emails are encrypted at rest.
- Users can delete raw email after parsing.
- Redact PII before any social features.

