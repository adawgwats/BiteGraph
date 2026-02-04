# Privacy & Security Policy

## Overview

BiteGraph processes sensitive food purchase data. This document outlines privacy safeguards, data retention, and user controls.

## Core Principles

1. **Default private**: Data is private by default; sharing requires explicit opt-in
2. **Minimal collection**: Only capture what's needed to classify and map foods
3. **Encrypted at rest**: Raw source data (emails, receipts) must be encrypted
4. **User control**: Users can delete raw data after interpretation
5. **Audit trails**: All interpretations are versioned and timestamped
6. **PII redaction**: Before social sharing, redact emails, addresses, order IDs, payment info

## Data Types

### Raw Source Data (Most Sensitive)

**What**: Original emails, PDF receipts, CSV exports, JSON payloads
**Why sensitive**: Contains customer names, addresses, full order history, timestamps
**Storage**: Encrypted object storage (AWS S3 + KMS or equivalent)
**Retention**: User can request deletion after parsing

### Normalized PurchaseLineItem

**What**: event_id, merchant_name, item_name_raw, quantity, price, timestamp, modifiers_raw
**Why sensitive**: Still identifies specific purchases, quantities, when bought
**Storage**: Encrypted (same as raw source)
**Retention**: Kept indefinitely unless user deletes

### Classified/Mapped Interpretations

**What**: vertical (food/non_food), food_kind, canonical_food_id, ingredient_profile_id
**Why sensitive**: Less PII, but still reveals eating patterns
**Storage**: Encrypted database
**Retention**: Kept indefinitely unless user deletes

### Aggregated/Statistical Data

**What**: "User eats pizza 3x/month", "Top 10 restaurants"
**Why sensitive**: Anonymous-looking, but could be de-anonymized
**Storage**: Standard database (no special encryption required if aggregated)
**Retention**: Per user settings

## Encryption

### At Rest

All raw source data and raw PurchaseLineItem records must be encrypted using:
- **Algorithm**: AES-256
- **Key management**: AWS KMS (customer-managed keys recommended)
- **Rotation**: Annual key rotation minimum

### In Transit

All API calls must use:
- **Protocol**: HTTPS/TLS 1.2+
- **Certificate**: Valid SSL certificate from recognized CA

## User Controls

### Deletion

Users can request:
1. **Delete raw source only**: Keep interpretations, delete original emails/receipts
2. **Delete everything**: Remove all data for a date range

Implementation:
```python
def delete_user_data(user_id: str, scope: Literal["raw", "all"], date_range: tuple):
    # Query all raw refs for user in date_range
    # Mark for deletion in KMS encrypted store
    # Re-run pipeline if needed (interpretations are deterministic)
```

### Export

Users can export:
- JSON dump of all food events (anonymized or full)
- CSV of historical food events

### Privacy Controls

- Toggle: "Share my journal with community" (default: OFF)
- Toggle: "Allow swap recommendations" (default: OFF)
- Blocklist: Merchants/items to exclude from sharing

## Social Layer (Help Requests + Swaps)

### Redaction Before Sharing

When user publishes a HelpRequest ("I eat too much pizza"), redact:

```python
REDACTION_RULES = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone": r"\d{3}[-.]?\d{3}[-.]?\d{4}",
    "address": r"\d+\s[\w\s]+(?:st|street|ave|avenue|rd|road)",
    "order_id": r"(order|order_id):\s*\w+",
    "payment": r"(card|payment|credit).*",
}

def redact_request(text: str) -> str:
    for name, pattern in REDACTION_RULES.items():
        text = re.sub(pattern, f"[{name.upper()}]", text, flags=re.I)
    return text
```

### Limits

- No full order history in public view (only aggregates)
- No merchant/item details beyond anonymized tags
- No timestamp granularity beyond "month"

Example public request:
```
"I want to eat less fried food this month. 
 Typical restaurants: [RESTAURANT], [RESTAURANT]
 Tags I eat too much: fried, salty
 Budget: $[PRICE] / week
 Dietary: none
```

Original data (not shared):
```
"I want to eat less fried food this month. 
 Typical restaurants: Shake Shack, McDonald's, Chick-fil-A
 Tags I eat too much: fried, salty
 Budget: $100 / week
 Dietary: none
 Email: user@example.com
 Address: 123 Main St, Anytown, USA"
```

## Compliance

### GDPR (EU Users)

- **Right to be forgotten**: Implement full deletion
- **Data portability**: Export feature required
- **Consent**: Explicit opt-in for data processing
- **DPA**: Have a Data Processing Agreement with AWS/hosting provider

### CCPA (California Users)

- **Right to know**: User can request all data
- **Right to delete**: User can request deletion
- **Right to opt-out**: Disable data sharing/selling
- **Disclosure**: Clear privacy policy

### HIPAA (If Health Features Added)

- If integrating health/medical data, may need HIPAA compliance
- Encryption, audit trails, business associate agreements

## API Security

### Authentication

- OAuth 2.0 or similar (no API keys in URLs)
- JWT tokens with short expiry (15 min) + refresh tokens (7 days)

### Rate Limiting

- 100 requests/min per user
- 1000 requests/min per IP
- Exponential backoff on failures

### Input Validation

- Max upload size: 10 MB per order export
- Max items per order: 1000
- Reject malformed JSON with clear error

## Audit & Monitoring

### Logging

Log all:
- User login/logout
- Data access (who accessed what, when)
- Deletion requests
- Interpretation changes (provenance audit trail)

Exclude from logs:
- Passwords, API keys, payment info
- Full email addresses (hash instead)
- Item names or merchant details (hash or redact)

### Monitoring

- Alert on: Bulk exports, deletion of historical data, unusual access patterns
- Dashboard: Data retention by user, deletion requests, compliance metrics

## Data Retention

| Data Type | Default Retention | User Override |
|-----------|-------------------|---------------|
| Raw source (emails, receipts) | 30 days | Can delete anytime |
| PurchaseLineItem | 7 years | Can delete by date range |
| Interpretations | 7 years | Can delete by date range |
| Access logs | 1 year | Not deletable (compliance) |
| Social posts (public) | Until user deletes | User can delete |

## Questions or Concerns?

Report security vulnerabilities to security@flavcliq.com (not a public issue).
Contact privacy@flavcliq.com for data requests.

---

**Version**: 1.0  
**Last Updated**: 2026-02-02  
**Next Review**: 2026-08-02
