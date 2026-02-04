"""Uber Eats order export adapter."""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser

from bitegraph.core.interfaces import Adapter
from bitegraph.core.models import PurchaseLineItem


class UberEatsAdapter:
    """
    Adapter for Uber Eats order exports (CSV format).

    Expected columns include (case/underscore tolerant):
    - Restaurant_Name
    - Request_Time_Local
    - Order_Status
    - Item_Name
    - Item_quantity
    - Customizations
    - Item_Price
    - Order_Price
    - Currency
    """

    def source_id(self) -> str:
        return "uber_eats"

    def can_parse(self, metadata: dict[str, Any]) -> bool:
        """Check if this is Uber Eats data."""
        return metadata.get("source") == "uber_eats" or metadata.get("format") == "uber_eats_csv"

    def parse(self, raw_bytes: bytes, metadata: dict[str, Any]) -> list[PurchaseLineItem]:
        """
        Parse Uber Eats CSV export into PurchaseLineItem records.

        Args:
            raw_bytes: Raw CSV bytes
            metadata: Context (user_id, source, file path)

        Returns:
            List of PurchaseLineItem records

        Raises:
            ValueError: If parsing fails
        """
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Failed to decode Uber Eats CSV: {exc}")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("Uber Eats CSV has no header row")

        items: list[PurchaseLineItem] = []
        user_id = metadata.get("user_id")
        raw_ref = metadata.get("raw_ref") or metadata.get("file_path") or "ubereats_export.csv"
        include_non_completed = bool(metadata.get("include_non_completed"))

        payload_hash = hashlib.sha256(raw_bytes).hexdigest()

        for row in reader:
            normalized: dict[str, str] = {}
            for key, value in row.items():
                if key is None:
                    continue
                normalized[self._normalize_header(key)] = value or ""

            order_status = normalized.get("order_status", "").lower().strip()
            if order_status and not include_non_completed:
                if order_status not in {"completed", "delivered"}:
                    continue

            restaurant = normalized.get("restaurant_name") or normalized.get("restaurant") or "Unknown"
            request_time = normalized.get("request_time_local") or normalized.get("request_time")
            item_name = normalized.get("item_name") or normalized.get("item") or ""
            quantity = self._safe_float(normalized.get("item_quantity") or normalized.get("quantity"), default=1.0)
            item_price = self._safe_float(normalized.get("item_price"), default=0.0)
            order_price = self._safe_float(normalized.get("order_price"), default=0.0)
            currency = normalized.get("currency")

            timestamp = self._parse_timestamp(request_time)

            modifiers = self._parse_modifiers(normalized.get("customizations") or normalized.get("customization"))

            order_id = normalized.get("order_id") or ""
            if not order_id:
                order_key = f"{restaurant}|{request_time}|{order_price}|{currency}"
                if order_key.strip("|"):
                    order_id = hashlib.sha256(order_key.encode("utf-8")).hexdigest()[:12]

            event_id_input = self._event_id_input(
                source="uber_eats",
                merchant=restaurant,
                timestamp=request_time or "",
                item_name=item_name,
                modifiers=modifiers,
                line_total=item_price,
                order_id=order_id,
            )
            event_id = hashlib.sha256(event_id_input.encode("utf-8")).hexdigest()[:16]

            if quantity <= 0:
                quantity = 1.0

            unit_price = item_price / quantity if quantity else item_price

            items.append(
                PurchaseLineItem(
                    event_id=event_id,
                    user_id=user_id,
                    source="uber_eats",
                    merchant_name=restaurant,
                    timestamp=timestamp,
                    item_name_raw=item_name,
                    modifiers_raw=modifiers if modifiers else None,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=item_price,
                    raw_ref=raw_ref,
                    raw_payload_hash=payload_hash,
                )
            )

        return items

    def _normalize_header(self, value: str) -> str:
        return "_".join(value.strip().lower().split())

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return date_parser.isoparse(value)
        except (ValueError, TypeError):
            return None

    def _parse_modifiers(self, value: str | None) -> list[str]:
        if not value:
            return []
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]

    def _safe_float(self, value: str | None, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _event_id_input(
        self,
        source: str,
        merchant: str,
        timestamp: str,
        item_name: str,
        modifiers: list[str] | None,
        line_total: float,
        order_id: str | None = None,
    ) -> str:
        mod_value = ",".join(modifiers or [])
        base = f"{source}|{merchant}|{timestamp}|{item_name}|{mod_value}|{line_total}"
        if order_id:
            base = f"{base}|{order_id}"
        return base
