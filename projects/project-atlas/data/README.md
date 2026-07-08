# Project Atlas — Phase 0 Data Store

This directory is the proprietary dataset — the actual asset Phase 0 exists to build. It is deliberately primitive: newline-delimited JSON, committed to this private repo. At hand-entry volumes, git *is* the database (history, backup, diff review), and every record is schema-validated on the way in.

| File | Contents | Schema |
|---|---|---|
| `listings.ndjson` | Real listings observed in the market | `../schemas/listing.schema.json` |
| `sold_transactions.ndjson` | Real completed sales (training truth) | `../schemas/sold_transaction.schema.json` |
| `calibration.json` | Fitted depreciation-curve constants, written by the calibration script | — |

## Workflow

```bash
# 1. Log a listing or sold comp you found (auction result, dealer page, etc.)
python3 tools/atlas_data.py new listing -o l.json   # or: new sold
# ... fill in the CHANGE_ME fields and real values ...
python3 tools/atlas_data.py add l.json               # validates, then appends
python3 tools/atlas_data.py list                     # see what's accumulated

# 2. Once a category has 20+ sold comps, fit its depreciation curve
python3 tools/calibrate_residual_curve.py

# 3. Generate the Top Buys report from real listings
python3 tools/daily_report.py                        # or --demo for the format preview
```

Records that still contain `CHANGE_ME` placeholders, fail schema validation, or duplicate an existing ID are rejected — a half-edited template cannot slip into the store.

## Rules

- **Never hand-edit the `.ndjson` files.** Add via `tools/atlas_data.py` so validation always runs. Corrections: fix the source JSON and re-add under a new ID, or edit via a follow-up commit with the diff reviewed.
- **Sold comps are the priority.** Listings are signals; sold transactions are labels (see `../schemas/README.md`). Calibration and every future model depend on comps first.
- **Log the boring ones too.** A comp that sold exactly at ask is as much training signal as a screaming deal — recording only exciting outcomes biases every model trained on this data.
