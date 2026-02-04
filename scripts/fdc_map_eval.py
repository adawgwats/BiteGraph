"""Evaluate mapping coverage against USDA FoodData Central (FDC).

Supports:
- API search (requires API key)
- Local CSV dataset search (fast, offline)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

DEFAULT_KIND_TO_TYPES = {
    "prepared_meal": ["FNDDS", "SR Legacy", "Foundation"],
    "grocery_packaged": ["Branded"],
    "grocery_raw": ["Foundation", "SR Legacy"],
    "beverage": ["FNDDS", "SR Legacy", "Foundation"],
}

TOKEN_LIMIT = 3
MIN_TOKEN_LEN = 3

LOCAL_TYPE_MAP = {
    "Branded": "branded_food",
    "Foundation": "foundation_food",
    "SR Legacy": "sr_legacy_food",
    "FNDDS": "survey_fndds_food",
}

@dataclass(frozen=True)
class ItemRow:
    item_name: str
    merchant_name: str
    food_kind: str | None


@dataclass(frozen=True)
class MatchResult:
    item_name: str
    merchant_name: str
    food_kind: str | None
    data_types: tuple[str, ...]
    fdc_id: int | None
    description: str | None
    data_type: str | None
    brand_owner: str | None
    brand_name: str | None
    score: float
    candidates: int = 0


@dataclass(frozen=True)
class FdcRecord:
    fdc_id: int
    data_type: str
    description: str
    description_norm: str


def normalize(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_key(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize(text: str) -> list[str]:
    tokens = normalize(text).split()
    tokens = [t for t in tokens if len(t) >= MIN_TOKEN_LEN]
    return tokens


def load_items(path: Path) -> list[ItemRow]:
    if path.suffix.lower() == ".jsonl":
        return _load_items_jsonl(path)
    return _load_items_csv(path)


def _load_items_csv(path: Path) -> list[ItemRow]:
    items: list[ItemRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            item_name = (row.get("Item_Name") or "").strip()
            merchant_name = (row.get("Restaurant_Name") or "").strip()
            if not item_name:
                continue
            items.append(ItemRow(item_name=item_name, merchant_name=merchant_name, food_kind=None))
    return items


def _load_items_jsonl(path: Path) -> list[ItemRow]:
    items: list[ItemRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            item = record.get("item", {})
            interpretation = record.get("interpretation", {}) or {}
            classification = record.get("classification", {}) or {}
            item_name = (item.get("item_name_raw") or "").strip()
            merchant_name = (item.get("merchant_name") or "").strip()
            food_kind = interpretation.get("food_kind") or classification.get("food_kind")
            if not item_name:
                continue
            items.append(ItemRow(item_name=item_name, merchant_name=merchant_name, food_kind=food_kind))
    return items


def load_cache(cache_path: Path) -> dict[str, list[dict]]:
    cache: dict[str, list[dict]] = {}
    if not cache_path.exists():
        return cache
    with cache_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            key = record.get("key")
            if key:
                cache[key] = record.get("foods", [])
    return cache


def append_cache(cache_path: Path, key: str, foods: list[dict]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"key": key, "foods": foods}) + "\n")


def fetch_fdc(
    query: str,
    data_types: list[str],
    api_key: str,
    page_size: int,
) -> list[dict]:
    payload = {
        "query": query,
        "pageSize": page_size,
        "dataType": data_types,
    }
    body = json.dumps(payload).encode("utf-8")
    url = f"{API_URL}?api_key={api_key}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    foods = []
    for food in data.get("foods", []) or []:
        foods.append(
            {
                "fdcId": food.get("fdcId"),
                "description": food.get("description"),
                "dataType": food.get("dataType"),
                "brandOwner": food.get("brandOwner"),
                "brandName": food.get("brandName"),
            }
        )
    return foods


def fetch_with_retry(
    query: str,
    data_types: list[str],
    api_key: str,
    page_size: int,
    retries: int,
    retry_sleep: float,
) -> list[dict]:
    attempt = 0
    while True:
        try:
            return fetch_fdc(query, data_types, api_key, page_size)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < retries:
                attempt += 1
                time.sleep(retry_sleep * attempt)
                continue
            raise




def map_local_types(data_types: list[str]) -> list[str]:
    mapped: list[str] = []
    for value in data_types:
        mapped.append(LOCAL_TYPE_MAP.get(value, value))
    return mapped

def pick_data_types(food_kind: str | None, fallback: list[str]) -> list[str]:
    if not food_kind:
        return fallback
    return DEFAULT_KIND_TO_TYPES.get(food_kind, fallback)


def limit_items(
    items: list[ItemRow],
    max_items: int | None,
    max_unique: int | None,
    unique_only: bool,
) -> list[ItemRow]:
    if unique_only or max_unique:
        seen = set()
        limited: list[ItemRow] = []
        for item in items:
            key = (item.item_name, item.food_kind)
            if key in seen:
                continue
            seen.add(key)
            limited.append(item)
            if max_unique and len(limited) >= max_unique:
                return limited
        items = limited
    if max_items:
        return items[:max_items]
    return items


def load_local_index(
    fdc_dir: Path,
    allowed_types: set[str],
) -> tuple[list[FdcRecord], dict[str, list[int]], float]:
    food_path = fdc_dir / "food.csv"
    if not food_path.exists():
        raise FileNotFoundError(f"food.csv not found in {fdc_dir}")

    start = time.perf_counter()
    records: list[FdcRecord] = []
    token_index: dict[str, list[int]] = {}

    with food_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            data_type = (row.get("data_type") or "").strip()
            if data_type not in allowed_types:
                continue
            description = (row.get("description") or "").strip()
            if not description:
                continue
            fdc_id = int(row.get("fdc_id") or 0)
            desc_norm = normalize(description)
            record = FdcRecord(
                fdc_id=fdc_id,
                data_type=data_type,
                description=description,
                description_norm=desc_norm,
            )
            records.append(record)
            idx = len(records) - 1
            tokens = tokenize(description)[:TOKEN_LIMIT]
            for token in tokens:
                token_index.setdefault(token, []).append(idx)

    elapsed = time.perf_counter() - start
    return records, token_index, elapsed


def choose_candidates(tokens: list[str], token_index: dict[str, list[int]]) -> list[int]:
    lists = [(t, token_index[t]) for t in tokens if t in token_index]
    if not lists:
        return []
    lists.sort(key=lambda x: len(x[1]))
    candidates = set(lists[0][1])
    for _, idxs in lists[1:2]:
        candidates.update(idxs)
    return list(candidates)


def score_candidates_local(
    item_name: str,
    candidates: list[int],
    records: list[FdcRecord],
) -> tuple[FdcRecord | None, float]:
    best = None
    best_score = 0.0
    item_norm = normalize(item_name)
    for idx in candidates:
        record = records[idx]
        score = float(fuzz.WRatio(item_norm, record.description_norm))
        if score > best_score:
            best_score = score
            best = record
    return best, best_score


def evaluate(
    items: list[ItemRow],
    api_key: str,
    cache_path: Path,
    page_size: int,
    min_score: float,
    include_merchant: bool,
    max_requests: int | None,
    sleep_sec: float,
    fallback_types: list[str],
    retries: int,
    retry_sleep: float,
    local_records: list[FdcRecord] | None,
    token_index: dict[str, list[int]] | None,
    max_candidates: int | None,
) -> tuple[list[MatchResult], dict]:
    cache = load_cache(cache_path) if local_records is None else {}
    results: list[MatchResult] = []
    request_count = 0
    per_kind: dict[str, int] = {}
    matched_kind: dict[str, int] = {}
    candidate_sizes: list[int] = []

    map_start = time.perf_counter()
    for item in items:
        kind_key = item.food_kind or "unknown"
        per_kind[kind_key] = per_kind.get(kind_key, 0) + 1
        data_types = pick_data_types(item.food_kind, fallback_types)

        if local_records is not None and token_index is not None:
            data_types = map_local_types(data_types)
            tokens = tokenize(item.item_name)
            candidates = choose_candidates(tokens, token_index)
            if data_types:
                candidates = [
                    idx for idx in candidates if local_records[idx].data_type in data_types
                ]
            if max_candidates and len(candidates) > max_candidates:
                candidates = candidates[:max_candidates]
            candidates_used = len(candidates)
            candidate_sizes.append(candidates_used)
            best = None
            score = 0.0
            if candidates:
                best, score = score_candidates_local(item.item_name, candidates, local_records)
            if best and score >= min_score:
                matched_kind[kind_key] = matched_kind.get(kind_key, 0) + 1
                results.append(
                    MatchResult(
                        item_name=item.item_name,
                        merchant_name=item.merchant_name,
                        food_kind=item.food_kind,
                        data_types=tuple(data_types),
                        fdc_id=best.fdc_id,
                        description=best.description,
                        data_type=best.data_type,
                        brand_owner=None,
                        brand_name=None,
                        score=round(score, 2),
                        candidates=candidates_used,
                    )
                )
            else:
                results.append(
                    MatchResult(
                        item_name=item.item_name,
                        merchant_name=item.merchant_name,
                        food_kind=item.food_kind,
                        data_types=tuple(data_types),
                        fdc_id=None,
                        description=None,
                        data_type=None,
                        brand_owner=None,
                        brand_name=None,
                        score=round(score, 2),
                        candidates=candidates_used,
                    )
                )
            continue

        key = f"{item.item_name}|{','.join(data_types)}"
        foods = cache.get(key)
        if foods is None:
            fetched = False
            if max_requests is not None and request_count >= max_requests:
                foods = []
            else:
                try:
                    foods = fetch_with_retry(
                        item.item_name, data_types, api_key, page_size, retries, retry_sleep
                    )
                    fetched = True
                except urllib.error.HTTPError as exc:
                    foods = []
                    print(f"fdc_error item={item.item_name} status={exc.code}")
                except Exception as exc:  # noqa: BLE001
                    foods = []
                    print(f"fdc_error item={item.item_name} err={exc}")
                if fetched:
                    append_cache(cache_path, key, foods)
                request_count += 1
                if sleep_sec > 0:
                    time.sleep(sleep_sec)

        best_food = None
        best_score = 0.0
        item_norm = normalize(item.item_name)
        merchant_norm = normalize(item.merchant_name) if item.merchant_name else ""
        for cand in foods or []:
            desc = cand.get("description") or ""
            score = float(fuzz.WRatio(item_norm, normalize(desc)))
            if include_merchant and merchant_norm:
                brand = cand.get("brandOwner") or cand.get("brandName") or ""
                if brand:
                    brand_score = float(fuzz.WRatio(merchant_norm, normalize(brand)))
                    score = 0.8 * score + 0.2 * brand_score
            if score > best_score:
                best_score = score
                best_food = cand

        if best_food and best_score >= min_score:
            matched_kind[kind_key] = matched_kind.get(kind_key, 0) + 1
            results.append(
                MatchResult(
                    item_name=item.item_name,
                    merchant_name=item.merchant_name,
                    food_kind=item.food_kind,
                    data_types=tuple(data_types),
                    fdc_id=best_food.get("fdcId"),
                    description=best_food.get("description"),
                    data_type=best_food.get("dataType"),
                    brand_owner=best_food.get("brandOwner"),
                    brand_name=best_food.get("brandName"),
                    score=round(best_score, 2),
                    candidates=len(foods or []),
                )
            )
        else:
            results.append(
                MatchResult(
                    item_name=item.item_name,
                    merchant_name=item.merchant_name,
                    food_kind=item.food_kind,
                    data_types=tuple(data_types),
                    fdc_id=None,
                    description=None,
                    data_type=None,
                    brand_owner=None,
                    brand_name=None,
                    score=round(best_score, 2),
                    candidates=len(foods or []),
                )
            )

    mapping_sec = time.perf_counter() - map_start
    avg_item_ms = (mapping_sec / len(items) * 1000) if items else 0.0

    summary = {
        "total_items": len(items),
        "unique_items": len({(i.item_name, i.food_kind) for i in items}),
        "matched_items": sum(1 for r in results if r.fdc_id is not None),
        "match_rate": round(
            (sum(1 for r in results if r.fdc_id is not None) / len(results)) * 100,
            2,
        )
        if results
        else 0.0,
        "per_kind": per_kind,
        "matched_per_kind": matched_kind,
        "timing": {
            "mapping_sec": round(mapping_sec, 2),
            "avg_item_ms": round(avg_item_ms, 2),
        },
    }

    if candidate_sizes:
        summary["candidate_stats"] = {
            "avg": round(sum(candidate_sizes) / len(candidate_sizes), 2),
            "median": round(statistics.median(candidate_sizes), 2),
            "max": max(candidate_sizes),
        }

    return results, summary


def write_outputs(results: list[MatchResult], summary: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"summary": summary, "results": [r.__dict__ for r in results]}, indent=2),
        encoding="utf-8",
    )


def write_csv(results: list[MatchResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "item_name",
                "merchant_name",
                "food_kind",
                "data_types",
                "fdc_id",
                "description",
                "data_type",
                "brand_owner",
                "brand_name",
                "score",
                "candidates",
            ]
        )
        for row in results:
            writer.writerow(
                [
                    row.item_name,
                    row.merchant_name,
                    row.food_kind,
                    ",".join(row.data_types),
                    row.fdc_id,
                    row.description,
                    row.data_type,
                    row.brand_owner,
                    row.brand_name,
                    row.score,
                    row.candidates,
                ]
            )


def write_cache(results: list[MatchResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in results:
            if row.fdc_id is None:
                continue
            item_key = normalize_key(f"{row.merchant_name}#{row.item_name}")
            payload = {
                "item_key": item_key,
                "merchant_name": row.merchant_name,
                "item_name": row.item_name,
                "food_kind": row.food_kind,
                "fdc_id": row.fdc_id,
                "description": row.description,
                "data_type": row.data_type,
                "score": row.score,
            }
            handle.write(json.dumps(payload) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV or mapped.jsonl file")
    parser.add_argument("--api-key", default=os.environ.get("FDC_API_KEY", ""))
    parser.add_argument("--cache", default="data/fdc_cache.jsonl")
    parser.add_argument("--output", default="out/fdc_mapping_report.json")
    parser.add_argument("--output-csv", default="out/fdc_mapping_report.csv")
    parser.add_argument("--output-cache", default="out/fdc_mapping_cache.jsonl")
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--min-score", type=float, default=70)
    parser.add_argument("--include-merchant", action="store_true")
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--max-unique", type=int, default=None)
    parser.add_argument("--unique-only", action="store_true")
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument(
        "--fallback-types",
        default="Branded,Foundation,FNDDS,SR Legacy",
        help="Comma-separated list used when food_kind is missing",
    )
    parser.add_argument(
        "--fdc-dir",
        default=None,
        help="Path to local FDC CSV directory (use local mapping if provided)",
    )
    parser.add_argument("--max-candidates", type=int, default=3000)
    args = parser.parse_args()

    api_key = args.api_key.strip() or "DEMO_KEY"
    if api_key == "DEMO_KEY" and not args.fdc_dir:
        print("warning: using DEMO_KEY (low rate limits). Set FDC_API_KEY for full run.")

    input_path = Path(args.input)
    items = load_items(input_path)
    items = limit_items(items, args.max_items, args.max_unique, args.unique_only)

    fallback_types = [t.strip() for t in args.fallback_types.split(",") if t.strip()]
    allowed_types = set(fallback_types)
    for values in DEFAULT_KIND_TO_TYPES.values():
        allowed_types.update(values)

    local_allowed_types = {LOCAL_TYPE_MAP.get(t, t) for t in allowed_types}

    local_records = None
    token_index = None
    index_sec = 0.0
    if args.fdc_dir:
        fdc_dir = Path(args.fdc_dir)
        local_records, token_index, index_sec = load_local_index(fdc_dir, local_allowed_types)
        print(f"local_index_records={len(local_records)} build_sec={index_sec:.2f}")

    results, summary = evaluate(
        items,
        api_key=api_key,
        cache_path=Path(args.cache),
        page_size=args.page_size,
        min_score=args.min_score,
        include_merchant=args.include_merchant,
        max_requests=args.max_requests,
        sleep_sec=args.sleep,
        fallback_types=fallback_types,
        retries=args.retries,
        retry_sleep=args.retry_sleep,
        local_records=local_records,
        token_index=token_index,
        max_candidates=args.max_candidates,
    )

    if args.fdc_dir:
        summary.setdefault("timing", {})["index_build_sec"] = round(index_sec, 2)

    write_outputs(results, summary, Path(args.output))
    write_csv(results, Path(args.output_csv))
    write_cache(results, Path(args.output_cache))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
