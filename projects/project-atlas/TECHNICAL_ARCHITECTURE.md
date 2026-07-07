# Project Atlas — Technical Architecture

This describes what actually exists in this repository today, not aspirational infrastructure. Where something is planned but not built, it's labeled as such rather than presented as if it were running.

## What this project currently is

A set of JSON Schema (draft 2020-12) data contracts plus a small library of Python scoring/decoding modules. There is no deployed service, no database, no crawler, and no live data source. Everything here is either (a) a validated schema a future ingestion/storage layer would conform to, or (b) a runnable, self-tested Python module implementing one deterministic calculation.

## Schema layer (`schemas/`)

Eight JSON Schema files define the canonical records:

| Schema | Represents |
|---|---|
| `taxonomy.schema.json` + `categories.seed.json` | Controlled category vocabulary |
| `listing.schema.json` | One observed listing (raw payload + normalized view) |
| `sold_transaction.schema.json` | A completed sale — training truth for valuation |
| `asset_identity.schema.json` | A decoded physical unit (VIN/PIN/serial/UDI/tail number), joining an asset across every listing/sale it appears in |
| `logistics_friction.schema.json` | Transport, repair, cleaning, tax, fee estimates for one listing |
| `regional_demand.schema.json` | (region, category, period) supply/demand/macro feature table |
| `training_labels.schema.json` | Frozen (prediction, outcome) pairs for the Buy Score model |
| `market_event.schema.json` | Detected disposition events (bankruptcy auctions, fleet refreshes, etc.) explaining *why* a price exists |

Every schema validates against the JSON Schema 2020-12 meta-schema (checked via `jsonschema.Draft202012Validator.check_schema` in Python — see Verification below). The full join map and design-decision log live in `schemas/README.md`; this document doesn't duplicate it. `schemas/DATA_DICTIONARY.md` is auto-generated from these eight files (`schemas/generate_data_dictionary.py`) — currently 332 fields — and should be regenerated, never hand-edited, whenever a schema changes.

Two recurring architectural patterns worth calling out here because they shape everything else:

1. **Vendor/provider integrations are modeled as generic arrays** (`listing.verification.sources`, `listing.comparables.provider_valuations`), never one hardcoded field per vendor. Adding EquipmentWatch, Sandhills, or a future provider is a data change, not a schema migration.
2. **Category-specific technical specs live in free-form objects** (`asset.spec_attributes`), not named fields on the universal schema — a field like `track_width_inches` doesn't generalize to an MRI machine or aircraft. Genuinely universal signals (like telematics hours/idle/fuel, which apply to any powered asset) are the exception and do get named fields (`asset.telematics`).

## Point-in-time correctness

Every time-varying schema carries an AS-OF timestamp (`regional_demand.computed_at`, `logistics_friction.computed_at`, `listing.asset.telematics.reported_at`, `sold_transaction.source.captured_at`/`sale.sold_at`) distinct from the period a row *describes*. `ml/point_in_time.py` implements the join primitive — a `PointInTimeIndex` (bisect-based single lookups) and a `sort_merge_as_of_join` (single forward pass for building a full training table) — that any future training pipeline must use to join features to a training example, instead of joining against the current/live state of a time-varying table. This is the same leakage-prevention principle already applied to `training_labels.prediction_snapshot` (frozen at prediction time), generalized to every joined feature. See `schemas/README.md`'s "Point-in-time join contract" section for the full field list.

## `ml/` — real code vs. framework specs

Two different bars apply here, and it matters which one a given file meets:

**Real, runnable, stdlib-only, self-tested** (no external dependencies — verified by actually executing them, not just syntax-checking):
- `buy_score.py` — the Buy Score combiner. Reproduces a worked example exactly (97.8/buy_now, 62.4/pass) when run.
- `pin_iso10261.py` — ISO 10261 PIN parser + Modulus-23 check-letter validator. Self-test proves round-trip validity and tamper detection. **Caveat: no authoritative AEM weight table was available; this is a documented, self-consistent scheme, not verified against a real OEM nameplate.**
- `transport_cost.py` — DAT-style linehaul + fuel surcharge + permit/escort/assembly cost formula.
- `residual_value_curve.py` — non-linear (exponential x power-decay) hours-driven depreciation curve. **Caveat: functional form and constants are illustrative placeholders pending calibration against real sold_transaction data.**
- `point_in_time.py` — AS-OF join utilities described above.
- `opportunity_engine.py` — chains all of the above over a small placeholder dataset into a ranked "Top N Buys" report. **This is a demo of the mechanism, not a live feed** — there is no scraper or auction API connected in this environment.

**Framework-dependent specs** (require xgboost/scikit-survival/torch, none of which are installed in this environment; these describe intended model architecture and are not executed here):
- `models/exit_price_model.py` — XGBoost regressor (Model I)
- `models/days_to_sell_model.py` — Random Survival Forest (Model II)
- `models/condition_cnn.py` — dual-head ResNet-50 (Model III)

`buy_score_model.md` documents which model handles which sub-task and why (e.g. GBTs over deep learning for tabular data with monotonic priors; survival analysis over plain regression because unsold listings are censored, not missing).

## Current vertical focus

Per an explicit strategy decision to narrow scope before broadening it, `schemas/priority_models.seed.json` lists 11 specific SKUs (Bobcat S650/S76/T76, CAT 259D3/289D3, Deere 317G/325G, Kubota SVL75/SVL97, Takeuchi TL10/TL12 — all compact track loaders/skid steers) as the initial focus, rather than building out the full multi-vertical category taxonomy. `opportunity_engine.py`'s placeholder dataset covers this same set.

## Not yet built

- **Ingestion**: no crawlers, no scraper infrastructure, no OEM telematics OAuth clients, no third-party API integrations (EquipmentWatch, Sandhills, Rouse, DAT). No credentials or access exist in this environment; building client code against them now would be non-functional stubs.
- **Storage**: no database. The schemas describe what a Postgres/ClickHouse/object-store layer would eventually validate against.
- **Feature store**: `point_in_time.py` is the join *algorithm*; there's no actual feature store service, no scheduled backfill jobs, no materialized training tables.
- **Model training**: no models have been trained. The XGBoost/RSF/ResNet specs are architecture decisions, not fitted models.
- **Telematics history**: `listing.asset.telematics` is a point-in-time snapshot; a proper time-series telematics table (needed for real trend features, not just latest-known-value) doesn't exist.
- **Portfolio Intelligence, Autonomous Agent, Marketplace** (escrow/insurance/financing): not schematized at all yet.
- **Global Physical Asset Index**: documented as a future direction in `PRD.md`, no schema.
- **Business financials** (TAM/SAM/SOM, capital requirements, unit economics): intentionally not fabricated without real market data.

## Verification

- Every schema: `jsonschema.Draft202012Validator.check_schema()` + at least one hand-built example record validated against it.
- Every stdlib-only `ml/*.py` module: executed directly (`python3 <module>.py`), asserting on self-test output, not just imported.
- `schemas/generate_data_dictionary.py`: run and its row count/structure spot-checked.
