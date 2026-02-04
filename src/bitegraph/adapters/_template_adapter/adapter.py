"""
Template adapter: copy this directory to create a new adapter for a different source.

This is a working example that parses a simple CSV format.
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser

from bitegraph.core.models import PurchaseLineItem


class TemplateAdapter:
    """Template adapter: implement these methods to support a new source."""

    def source_id(self) -> str:
        return "template_source"

    def can_parse(self, metadata: dict[str, Any]) -> bool:
        return metadata.get("source") == self.source_id() or metadata.get("format") == "template_csv"

    def parse(self, raw_bytes: bytes, metadata: dict[str, Any]) -> list[PurchaseLineItem]:
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Failed to decode template CSV: {exc}")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("Template CSV has no header row")

        items: list[PurchaseLineItem] = []
        user_id = metadata.get("user_id")
        raw_ref = metadata.get("raw_ref") or metadata.get("file_path") or "template.csv"
        payload_hash = hashlib.sha256(raw_bytes).hexdigest()

        for row in reader:
            merchant = (row.get("merchant_name") or row.get("merchant") or "Unknown").strip()
            item_name = (row.get("item_name") or row.get("item") or "").strip()
            quantity = self._safe_float(row.get("quantity"), default=1.0)
            unit_price = self._safe_float(row.get("unit_price"), default=0.0)
            line_total = self._safe_float(row.get("line_total"), default=unit_price * quantity)
            timestamp = self._parse_timestamp(row.get("timestamp"))

            event_id_input = f"{self.source_id()}|{merchant}|{row.get('timestamp','')}|{item_name}|{line_total}"
            event_id = hashlib.sha256(event_id_input.encode("utf-8")).hexdigest()[:16]

            items.append(
                PurchaseLineItem(
                    event_id=event_id,
                    user_id=user_id,
                    source=self.source_id(),
                    merchant_name=merchant,
                    timestamp=timestamp,
                    item_name_raw=item_name,
                    modifiers_raw=None,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                    raw_ref=raw_ref,
                    raw_payload_hash=payload_hash,
                )
            )

        return items

    def _safe_float(self, value: str | None, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return date_parser.isoparse(value)
        except (ValueError, TypeError):
            return None
