import argparse
import csv
import json
import re
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
from rapidfuzz import fuzz, process

SHOP_TO_CATEGORY = {
    "supermarket": "grocery_packaged",
    "grocery": "grocery_packaged",
    "convenience": "grocery_packaged",
    "deli": "grocery_packaged",
    "bakery": "grocery_packaged",
    "farm": "grocery_raw",
    "alcohol": "grocery_packaged",
    "beverages": "grocery_packaged",
    "greengrocer": "grocery_raw",
}

AMENITY_TO_CATEGORY = {
    "restaurant": "prepared_meal",
    "fast_food": "prepared_meal",
    "food_court": "prepared_meal",
    "cafe": "beverage",
    "ice_cream": "beverage",
    "bar": "beverage",
    "pub": "beverage",
}

DEFAULT_OVERRIDES = {
    "Washington D.C.": "WashingtonDC",
    "New York City": "NewYork",
    "Upstate NY": "NewYork",
}

STOPWORDS = {"city", "metro", "metropolitan", "area"}
DEFAULT_THRESHOLDS = [90, 85, 80, 75]


def normalize_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    tokens = [token for token in cleaned.split() if token and token not in STOPWORDS]
    return "".join(tokens)


def load_city_counts(orders_path: Path) -> Counter:
    counts: Counter = Counter()
    with orders_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            city = (row.get("City_Name") or "").strip()
            if city:
                counts[city] += 1
    return counts


def fetch_bbbike_regions() -> list[str]:
    url = "https://download.bbbike.org/osm/bbbike/"
    html = urllib.request.urlopen(url).read().decode("utf-8")
    return sorted(set(re.findall(r'href="([A-Za-z0-9_-]+)/"', html)))


def parse_thresholds(value: str) -> list[int]:
    thresholds: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            thresholds.append(int(token))
        except ValueError:
            continue
    return thresholds or DEFAULT_THRESHOLDS


def match_regions(
    cities: list[str],
    regions: list[str],
    overrides: dict[str, str],
    thresholds: list[int],
) -> tuple[dict[str, str], list[str], dict[str, dict[str, int | str]]]:
    matched: dict[str, str] = {}
    unmatched: list[str] = []
    meta: dict[str, dict[str, int | str]] = {}
    region_norm = {normalize_key(r): r for r in regions}
    region_list = list(region_norm.keys())

    for city in cities:
        if city in overrides:
            matched[city] = overrides[city]
            meta[city] = {"method": "override", "score": 100}
            continue

        city_norm = normalize_key(city)
        if city_norm in region_norm:
            matched[city] = region_norm[city_norm]
            meta[city] = {"method": "normalized_exact", "score": 100}
            continue

        best_match = None
        used_threshold = None
        for threshold in thresholds:
            best = process.extractOne(city_norm, region_list, scorer=fuzz.WRatio)
            if best and best[1] >= threshold:
                best_match = best
                used_threshold = threshold
                break

        if best_match:
            matched[city] = region_norm[best_match[0]]
            meta[city] = {"method": f"fuzzy_{used_threshold}", "score": int(best_match[1])}
        else:
            unmatched.append(city)

    return matched, unmatched, meta


def download_region(region: str, out_dir: Path) -> tuple[Path, float, bool]:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{region}.osm.parquet.zip"
    url = f"https://download.bbbike.org/osm/bbbike/{region}/{region}.osm.parquet.zip"
    start = time.perf_counter()
    downloaded = False
    if not zip_path.exists():
        urllib.request.urlretrieve(url, zip_path)
        downloaded = True
    return zip_path, time.perf_counter() - start, downloaded


def extract_region(zip_path: Path, out_dir: Path, region: str) -> tuple[Path, float, bool]:
    region_dir = out_dir / region
    parquet_root = region_dir / f"{region}-parquet" / "parquet"
    if parquet_root.exists() and any(parquet_root.rglob("*.parquet")):
        return parquet_root, 0.0, False

    start = time.perf_counter()
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(region_dir)
    return parquet_root, time.perf_counter() - start, True


def categorize_row(shop: str | None, amenity: str | None) -> str:
    if shop:
        category = SHOP_TO_CATEGORY.get(shop)
        if category:
            return category
    if amenity:
        category = AMENITY_TO_CATEGORY.get(amenity)
        if category:
            return category
    return "other_commercial"


def query_region(parquet_root: Path, output_dir: Path, region: str) -> tuple[int, float, dict[str, int]]:
    start = time.perf_counter()
    glob_path = parquet_root / "type=*" / "*.parquet"
    con = duckdb.connect()
    rows = con.execute(
        """
        SELECT tags['name'] AS name, tags['shop'] AS shop, tags['amenity'] AS amenity
        FROM read_parquet(?::VARCHAR)
        WHERE map_contains(tags, 'name')
          AND (map_contains(tags, 'shop') OR map_contains(tags, 'amenity'))
        """,
        [str(glob_path).replace('\\', '/')],
    ).fetchall()

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{region}_merchant_index.csv"
    counts: Counter = Counter()
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("name,shop,amenity,category\n")
        for name, shop, amenity in rows:
            category = categorize_row(shop, amenity)
            counts[category] += 1
            safe_name = (name or "").replace("\"", "\"\"")
            safe_shop = (shop or "").replace("\"", "\"\"")
            safe_amenity = (amenity or "").replace("\"", "\"\"")
            handle.write(f"\"{safe_name}\",\"{safe_shop}\",\"{safe_amenity}\",{category}\n")

    return len(rows), time.perf_counter() - start, dict(counts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", required=True)
    parser.add_argument("--output", default="data/osm")
    parser.add_argument("--thresholds", default="90,85,80,75")
    parser.add_argument("--suggestions", type=int, default=0)
    args = parser.parse_args()

    orders_path = Path(args.orders)
    output_base = Path(args.output)

    city_counts = load_city_counts(orders_path)
    print("cities_detected:")
    for name, count in city_counts.most_common():
        print(f"  {name}: {count}")

    regions = fetch_bbbike_regions()
    thresholds = parse_thresholds(args.thresholds)
    matched, unmatched, meta = match_regions(list(city_counts.keys()), regions, DEFAULT_OVERRIDES, thresholds)

    if unmatched:
        print("unmatched_cities:")
        for city in unmatched:
            print(f"  {city}")

    if unmatched and args.suggestions > 0:
        region_norm = {normalize_key(r): r for r in regions}
        region_list = list(region_norm.keys())
        print("suggested_regions:")
        for city in unmatched:
            city_norm = normalize_key(city)
            suggestions = process.extract(city_norm, region_list, scorer=fuzz.WRatio, limit=args.suggestions)
            if not suggestions:
                continue
            formatted = ", ".join(
                f"{region_norm[choice]} ({score})" for choice, score, _ in suggestions
            )
            print(f"  {city}: {formatted}")

    print("matched_regions:")
    for city, region in matched.items():
        info = meta.get(city, {})
        method = info.get("method", "")
        score = info.get("score", "")
        suffix = f" ({method}, {score})" if method else ""
        print(f"  {city} -> {region}{suffix}")

    region_to_cities = defaultdict(list)
    region_to_city_matches = defaultdict(list)
    for city, region in matched.items():
        region_to_cities[region].append(city)
        info = meta.get(city, {})
        region_to_city_matches[region].append({
            "city": city,
            "method": info.get("method", ""),
            "score": info.get("score", 0),
        })

    results = []
    for region, cities in region_to_cities.items():
        region_dir = output_base / region
        zip_path, download_time, downloaded = download_region(region, region_dir)
        parquet_root, extract_time, extracted = extract_region(zip_path, output_base, region)
        row_count, query_time, category_counts = query_region(parquet_root, output_base / "indexes", region)

        results.append(
            {
                "cities": cities,
                "city_matches": region_to_city_matches[region],
                "region": region,
                "downloaded": downloaded,
                "download_sec": round(download_time, 2),
                "extracted": extracted,
                "extract_sec": round(extract_time, 2),
                "rows": row_count,
                "query_sec": round(query_time, 2),
                "categories": category_counts,
            }
        )
        print(
            f"region={region} rows={row_count} download_sec={download_time:.2f} "
            f"extract_sec={extract_time:.2f} query_sec={query_time:.2f}"
        )

    summary_path = output_base / "indexes" / "region_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"summary_written={summary_path}")


if __name__ == "__main__":
    main()
