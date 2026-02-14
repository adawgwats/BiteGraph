"""CLI helpers for BiteGraph."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

from bitegraph.adapters.ubereats import UberEatsAdapter
from bitegraph.core.classify_rules import RuleBasedClassifier
from bitegraph.core.consume_infer import DefaultConsumptionInference
from bitegraph.core.map_templates import TemplateIngredientMapper
from bitegraph.core.nutrition_flavor import TemplateNutritionFlavorEnricher
from bitegraph.core.interfaces import Adapter
from bitegraph.core.models import (
    ClassificationResult,
    FoodKind,
    FoodVertical,
    PurchaseLineItem,
)
from bitegraph.core.pipeline import PipelineRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bitegraph")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subparsers.add_parser("parse", help="Parse raw export into normalized JSONL")
    parse_cmd.add_argument("file")
    parse_cmd.add_argument("--source", required=True)
    parse_cmd.add_argument("--out", required=True)
    parse_cmd.add_argument("--user-id", default="")

    classify_cmd = subparsers.add_parser("classify", help="Classify normalized JSONL")
    classify_cmd.add_argument("file")
    classify_cmd.add_argument("--out", required=True)
    classify_cmd.add_argument("--assume-food", action="store_true")

    map_cmd = subparsers.add_parser("map", help="Map classified JSONL")
    map_cmd.add_argument("file")
    map_cmd.add_argument("--out", required=True)

    pipeline_cmd = subparsers.add_parser("pipeline", help="Run end-to-end pipeline")
    pipeline_cmd.add_argument("file")
    pipeline_cmd.add_argument("--source", required=True)
    pipeline_cmd.add_argument("--out-dir", required=True)
    pipeline_cmd.add_argument("--user-id", default="")
    pipeline_cmd.add_argument("--assume-food", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "parse":
        items = _parse_file(args.file, args.source, args.user_id)
        _write_jsonl(args.out, [dataclass_to_dict(i) for i in items])
        return 0

    if args.command == "classify":
        items = [parse_purchase_line_item(obj) for obj in _read_jsonl(args.file)]
        classifier = RuleBasedClassifier(assume_food_if_priced=args.assume_food)
        records = []
        for item in items:
            classification = classifier.classify(item)
            records.append(
                {
                    "item": dataclass_to_dict(item),
                    "classification": dataclass_to_dict(classification),
                }
            )
        _write_jsonl(args.out, records)
        return 0

    if args.command == "map":
        mapper = TemplateIngredientMapper()
        records = []
        for obj in _read_jsonl(args.file):
            item = parse_purchase_line_item(obj.get("item", {}))
            classification = parse_classification_result(obj.get("classification", {}))
            mapping = mapper.map(item, classification)
            records.append(
                {
                    "item": dataclass_to_dict(item),
                    "classification": dataclass_to_dict(classification),
                    "mapping": dataclass_to_dict(mapping),
                }
            )
        _write_jsonl(args.out, records)
        return 0

    if args.command == "pipeline":
        adapter = _adapter_for_source(args.source)
        runner = PipelineRunner(
            adapters=[adapter],
            classifier=RuleBasedClassifier(assume_food_if_priced=args.assume_food),
            mapper=TemplateIngredientMapper(),
            enricher=TemplateNutritionFlavorEnricher(),
            inference_engine=DefaultConsumptionInference(),
        )
        raw_bytes = Path(args.file).read_bytes()
        results = runner.run_pipeline(
            raw_bytes,
            {"source": args.source, "user_id": args.user_id, "file_path": args.file},
        )

        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        normalized = [dataclass_to_dict(r.item) for r in results]
        interpreted = [
            {
                "item": dataclass_to_dict(r.item),
                "classification": dataclass_to_dict(r.classification) if r.classification else None,
                "interpretation": dataclass_to_dict(r.interpretation) if r.interpretation else None,
            }
            for r in results
        ]
        mapped = [
            {
                "item": dataclass_to_dict(r.item),
                "classification": dataclass_to_dict(r.classification) if r.classification else None,
                "mapping": dataclass_to_dict(r.mapping) if r.mapping else None,
                "enrichment": dataclass_to_dict(r.enrichment) if r.enrichment else None,
                "consumption": dataclass_to_dict(r.consumption) if r.consumption else None,
                "interpretation": dataclass_to_dict(r.interpretation) if r.interpretation else None,
            }
            for r in results
        ]

        _write_jsonl(out_dir / "normalized.jsonl", normalized)
        _write_jsonl(out_dir / "interpreted.jsonl", interpreted)
        _write_jsonl(out_dir / "mapped.jsonl", mapped)
        return 0

    return 1


def _adapter_for_source(source: str) -> Adapter:
    if source == "uber_eats":
        return UberEatsAdapter()
    raise ValueError(f"Unsupported source: {source}")


def _parse_file(file_path: str, source: str, user_id: str | None) -> list[PurchaseLineItem]:
    adapter = _adapter_for_source(source)
    raw_bytes = Path(file_path).read_bytes()
    return adapter.parse(raw_bytes, {"source": source, "user_id": user_id, "file_path": file_path})


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def dataclass_to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        data = asdict(obj)
        return {key: dataclass_to_dict(value) for key, value in data.items()}
    if isinstance(obj, list):
        return [dataclass_to_dict(value) for value in obj]
    if isinstance(obj, dict):
        return {key: dataclass_to_dict(value) for key, value in obj.items()}
    return obj


def parse_purchase_line_item(data: dict[str, Any]) -> PurchaseLineItem:
    return PurchaseLineItem(
        event_id=data.get("event_id", ""),
        user_id=data.get("user_id"),
        source=data.get("source", ""),
        merchant_name=data.get("merchant_name", ""),
        merchant_brand=data.get("merchant_brand") or data.get("merchant_name", ""),
        merchant_location=data.get("merchant_location"),
        timestamp=_parse_datetime(data.get("timestamp")),
        item_name_raw=data.get("item_name_raw", ""),
        modifiers_raw=data.get("modifiers_raw") or None,
        quantity=float(data.get("quantity", 1.0)),
        unit_price=float(data.get("unit_price", 0.0)),
        line_total=float(data.get("line_total", 0.0)),
        raw_ref=data.get("raw_ref", ""),
        raw_payload_hash=data.get("raw_payload_hash", ""),
    )


def parse_classification_result(data: dict[str, Any]) -> ClassificationResult:
    vertical_value = data.get("vertical", FoodVertical.UNKNOWN.value)
    food_kind_value = data.get("food_kind")
    return ClassificationResult(
        event_id=data.get("event_id", ""),
        vertical=FoodVertical(vertical_value),
        food_kind=FoodKind(food_kind_value) if food_kind_value else None,
        confidence=float(data.get("confidence", 0.0)),
        reasons=list(data.get("reasons", []) or []),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return date_parser.isoparse(str(value))
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
