# Template Adapter

This is a working example adapter. Copy this directory to start a new adapter.

## Input Format (CSV)

```csv
merchant_name,item_name,quantity,unit_price,timestamp
Sample Restaurant,Burger,1,9.99,2026-01-15T19:30:00Z
```

## Usage

```python
from bitegraph.adapters._template_adapter import TemplateAdapter

adapter = TemplateAdapter()
metadata = {"source": "template_source"}

with open("fixtures/sample_order.csv", "rb") as f:
    items = adapter.parse(f.read(), metadata)
```

## Notes

- This adapter is intentionally simple and safe for copy/paste.
- Replace the CSV parsing with logic for your real source.
