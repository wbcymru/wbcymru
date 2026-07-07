"""Phase 0 data-entry tooling: get real listings and sold comps into the
data store, validated against the canonical schemas.

The store is deliberately primitive -- newline-delimited JSON files under
data/ (data/listings.ndjson, data/sold_transactions.ndjson), committed to
the private repo. At Phase 0 volumes (tens to low hundreds of records,
entered by hand) a database would be infrastructure for its own sake;
the dataset itself is the asset, and git already gives it history,
backup, and diff review.

Workflow:
    python3 tools/atlas_data.py new listing -o my_listing.json
    # ... edit my_listing.json with the real values ...
    python3 tools/atlas_data.py add my_listing.json
    python3 tools/atlas_data.py list
"""

import argparse
import datetime
import json
import os
import sys
import uuid

from jsonschema import Draft202012Validator, FormatChecker

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(PROJECT_ROOT, "schemas")
DEFAULT_DATA_DIR = os.path.join(PROJECT_ROOT, "data")

KINDS = {
    "listing": {
        "schema": "listing.schema.json",
        "store": "listings.ndjson",
        "id_field": "record_id",
    },
    "sold": {
        "schema": "sold_transaction.schema.json",
        "store": "sold_transactions.ndjson",
        "id_field": "transaction_id",
    },
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_template(kind: str) -> dict:
    """Pre-filled record template. Placeholder values are chosen to FAIL
    validation until replaced (e.g. CHANGE_ME urls), so a half-edited
    template can't slip into the store."""
    now = _now_iso()
    if kind == "listing":
        return {
            "record_id": str(uuid.uuid4()),
            "source": {
                "platform": "CHANGE_ME e.g. IronPlanet / MachineryTrader / dealer name",
                "url": "CHANGE_ME_full_listing_url",
                "scraped_at": now,
                "first_seen_at": now,
                "listing_type": "auction",
                "status": "active",
            },
            "raw": {"note": "paste anything useful from the source page here, verbatim"},
            "asset": {
                "category": "skid_steer",
                "manufacturer": "CHANGE_ME",
                "model": "CHANGE_ME",
                "year": None,
                "serial_number": None,
                "vin": None,
                "hours": None,
                "miles": None,
                "attachments": [],
                "fuel_type": "diesel",
            },
            "condition": {
                "seller_condition": None,
                "inspection_available": False,
                "damage_notes": [],
                "photo_count": 0,
            },
            "location": {
                "city": None,
                "state": None,
                "state_iso_3166_2": None,
                "country": "US",
                "postal_code": None,
            },
            "pricing": {
                "currency": "USD",
                "current_bid": None,
                "buy_now_price": None,
                "asking_price": None,
                "reserve_met": None,
                "buyer_premium_pct": None,
                "estimated_fees": None,
            },
            "auction": {
                "start_at": None,
                "end_at": None,
                "bid_count": None,
                "watchers": None,
            },
            "friction": {
                "estimated_transport_cost": None,
                "estimated_repair_cost": None,
                "estimated_cleaning_cost": None,
                "estimated_tax": None,
                "total_friction_cost": None,
            },
            "scoring": {},
        }
    if kind == "sold":
        return {
            "transaction_id": str(uuid.uuid4()),
            "listing_record_id": None,
            "source": {
                "platform": "CHANGE_ME e.g. Ritchie Bros results / dealer reported",
                "captured_at": now,
                "origin": "auction_result",
                "raw": {"note": "paste the source result line/page content here"},
            },
            "asset": {
                "category": "skid_steer",
                "manufacturer": "CHANGE_ME",
                "model": "CHANGE_ME",
                "year": None,
                "serial_number": None,
                "vin": None,
                "hours": None,
                "miles": None,
                "condition_at_sale": None,
            },
            "location": {
                "city": None,
                "state": None,
                "country": "US",
                "postal_code": None,
            },
            "sale": {
                "sold_price": 0,
                "currency": "USD",
                "sold_price_usd": None,
                "sold_at": now,
                "sale_type": "auction_hammer",
                "auction_type": None,
                "valuation_basis": None,
                "buyer_type": None,
                "buyer_premium_pct": None,
                "days_on_market": None,
            },
        }
    raise ValueError(f"unknown kind {kind!r}")


def load_validator(kind: str) -> Draft202012Validator:
    with open(os.path.join(SCHEMA_DIR, KINDS[kind]["schema"])) as f:
        schema = json.load(f)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def store_path(kind: str, data_dir: str) -> str:
    return os.path.join(data_dir, KINDS[kind]["store"])


def existing_ids(kind: str, data_dir: str) -> set:
    path = store_path(kind, data_dir)
    ids = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    ids.add(json.loads(line)[KINDS[kind]["id_field"]])
    return ids


def detect_kind(record: dict) -> str:
    if "record_id" in record:
        return "listing"
    if "transaction_id" in record:
        return "sold"
    raise ValueError("record has neither record_id (listing) nor transaction_id (sold)")


def cmd_new(args):
    template = make_template(args.kind)
    text = json.dumps(template, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text + "\n")
        print(f"Template written to {args.output} -- edit the CHANGE_ME fields, then:")
        print(f"  python3 tools/atlas_data.py add {args.output}")
    else:
        print(text)


def cmd_add(args):
    os.makedirs(args.data_dir, exist_ok=True)
    validators = {}
    added, failed = 0, 0
    for path in args.files:
        with open(path) as f:
            record = json.load(f)
        kind = detect_kind(record)
        if kind not in validators:
            validators[kind] = load_validator(kind)
        errors = sorted(validators[kind].iter_errors(record), key=lambda e: list(e.path))
        placeholder_hits = [
            p for p in _find_placeholders(record)
        ]
        if errors or placeholder_hits:
            failed += 1
            print(f"REJECTED {path} ({kind}):")
            for e in errors:
                loc = ".".join(str(p) for p in e.path) or "<root>"
                print(f"  - {loc}: {e.message}")
            for loc in placeholder_hits:
                print(f"  - {loc}: still contains a CHANGE_ME placeholder")
            continue
        record_id = record[KINDS[kind]["id_field"]]
        if record_id in existing_ids(kind, args.data_dir):
            failed += 1
            print(f"REJECTED {path}: {KINDS[kind]['id_field']} {record_id} already in store")
            continue
        with open(store_path(kind, args.data_dir), "a") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
        added += 1
        print(f"ADDED {path} -> {store_path(kind, args.data_dir)}")
    print(f"\n{added} added, {failed} rejected")
    sys.exit(1 if failed else 0)


def _find_placeholders(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _find_placeholders(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _find_placeholders(v, f"{path}[{i}]")
    elif isinstance(obj, str) and "CHANGE_ME" in obj:
        yield path


def cmd_list(args):
    for kind, cfg in KINDS.items():
        path = store_path(kind, args.data_dir)
        if not os.path.exists(path):
            print(f"{cfg['store']}: 0 records")
            continue
        records = [json.loads(l) for l in open(path) if l.strip()]
        print(f"{cfg['store']}: {len(records)} records")
        for r in records:
            asset = r.get("asset", {})
            label = f"{asset.get('year') or '????'} {asset.get('manufacturer')} {asset.get('model')}"
            if kind == "listing":
                price = r.get("pricing", {})
                amount = price.get("buy_now_price") or price.get("asking_price") or price.get("current_bid")
                status = r.get("source", {}).get("status")
                print(f"  {r['record_id'][:8]}  {label:<30} {amount or '?':>10}  {status}")
            else:
                sale = r.get("sale", {})
                print(f"  {r['transaction_id'][:8]}  {label:<30} {sale.get('sold_price'):>10}  sold {sale.get('sold_at', '')[:10]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="override the data store directory (mainly for tests)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="emit a pre-filled record template")
    p_new.add_argument("kind", choices=list(KINDS))
    p_new.add_argument("-o", "--output", help="write template to a file instead of stdout")
    p_new.set_defaults(func=cmd_new)

    p_add = sub.add_parser("add", help="validate record file(s) and append to the store")
    p_add.add_argument("files", nargs="+")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="summarize the data store")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
