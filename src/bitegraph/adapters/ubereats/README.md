# Uber Eats Adapter

Parse Uber Eats order exports into normalized `PurchaseLineItem` records.

## Input Format (CSV)

```csv
City_Name,Restaurant_Name,Request_Time_Local,Final_Delivery_Time_Local,Order_Status,Item_Name,Item_quantity,Customizations,Customization_Cost_Local,Special_Instructions,Item_Price,Order_Price,Currency
Washington D.C.,Sample Restaurant,2026-01-15T19:30:00Z,2026-01-15T20:05:26Z,completed,Shroom Burger,1,"no pickles, extra mayo",0,,8.99,24.50,USD
```

## Usage

```python
from bitegraph.adapters.ubereats import UberEatsAdapter

adapter = UberEatsAdapter()
metadata = {"source": "uber_eats"}

with open("user_orders-0.csv", "rb") as f:
    items = adapter.parse(f.read(), metadata={"user_id": "user123"})

for item in items:
    print(item.event_id, item.merchant_name, item.item_name_raw)
```

## Notes

- CSV headers are normalized (spaces/underscores are tolerated).
- `Request_Time_Local` is parsed with ISO8601 handling (including `Z`).
- `Customizations` is split on commas into a list.
- `event_id` is a stable hash of: source + merchant + timestamp + item_name_raw + modifiers_raw + line_total (+ order_id if present).
