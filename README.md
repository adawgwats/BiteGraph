# BiteGraph

A modular engine that converts messy order/export data into normalized, classified, and mapped food events.

## Mission

BiteGraph extracts structured meaning from real-world order and purchase data:

- **Normalize** messy line items into canonical `PurchaseLineItem` events
- **Classify** food vs. non-food, plus food subtypes (prepared meal, grocery, beverage)
- **Map** raw ingredients with confidence scores and versioned overlays
- **Infer** consumption separately from purchases (groceries are not auto-consumed)
- **Extend** via adapters (Uber Eats, DoorDash, CSV, etc.)

## Scope

BiteGraph focuses on:

- Parsing raw purchase data into normalized events
- Classifying food vs non-food and food subtypes
- Mapping items to canonical foods and ingredient profiles with confidence and provenance

Out of scope:

- Downstream enrichment beyond ingredient profiles
- Application UI, recommendations, or infrastructure

## Local CI

Run the same checks as GitHub Actions before pushing:

- Cross-platform: `python -m bitegraph.ci` (or `bitegraph-ci` after install)
- Windows: `scripts\ci_local.ps1`
- macOS/Linux: `scripts/ci_local.sh`
## Quick Start

### Installation

```bash
pip install bitegraph-core
```

### Basic Usage

```python
from bitegraph.adapters.ubereats import UberEatsAdapter
from bitegraph.core.classify_rules import RuleBasedClassifier
from bitegraph.core.consume_infer import DefaultConsumptionInference
from bitegraph.core.map_templates import TemplateIngredientMapper
from bitegraph.core.pipeline import PipelineRunner

adapter = UberEatsAdapter()
runner = PipelineRunner(
    adapters=[adapter],
    classifier=RuleBasedClassifier(),
    mapper=TemplateIngredientMapper(),
    inference_engine=DefaultConsumptionInference(),
)

with open("user_orders-0.csv", "rb") as f:
    results = runner.run_pipeline(f.read(), {"source": "uber_eats", "user_id": "user123"})

for result in results:
    print(result.item.event_id, result.interpretation, result.consumption)
```

### CLI

```bash
# Parse a CSV export
python cli/bitegraph_cli.py parse user_orders-0.csv --source uber_eats --out normalized.jsonl

# Classify normalized items
python cli/bitegraph_cli.py classify normalized.jsonl --out interpreted.jsonl

# Map classified items
python cli/bitegraph_cli.py map interpreted.jsonl --out mapped.jsonl

# End-to-end pipeline
python cli/bitegraph_cli.py pipeline user_orders-0.csv --source uber_eats --out-dir out/
```

## Architecture

See `docs/architecture.md` for detailed design, integration contract, and JSONL schema.

## Contributing

See `CONTRIBUTING.md` for development setup and contribution guidelines.

## Privacy & Security

- Raw data is encrypted at rest and never persists longer than necessary
- All mappings are versioned and auditable
- See `docs/privacy.md` for detailed policies

## License

MIT
