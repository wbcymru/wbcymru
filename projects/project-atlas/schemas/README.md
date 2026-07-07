# Project Atlas — Data Schemas

Raw data schema first, ML model downstream. Bad schema = bad model. Build/review order:

1. `taxonomy.schema.json` + `categories.seed.json` — controlled vocabulary every `category` field draws from. `priority_models.seed.json` is a finer-grained, narrower list: specific make/model SKUs (Bobcat/CAT/Deere/Kubota/Takeuchi compact track loaders) the platform is deliberately focusing on first, per the "pick one vertical" strategy — not a taxonomy replacement.
2. `listing.schema.json` — normalized record for one observed listing. Raw source payload preserved verbatim under `raw`, normalized fields alongside it. Never overwrite `raw`.
3. `sold_transaction.schema.json` — ground truth. Listings are signals; sold transactions are labels.
4. `asset_identity.schema.json` — VIN/serial/PIN/UDI/tail-number decode, so the same physical unit can be tracked across multiple listings and resales over its lifetime.
5. `logistics_friction.schema.json` — transport, repair, cleaning, tax, fees. Source of truth for the `friction` block that `listing` denormalizes a snapshot of.
6. `regional_demand.schema.json` — (region, category, period) supply/demand/macro feature table for the Market Intelligence Engine.
7. `training_labels.schema.json` — frozen (prediction, outcome) pairs for the Buy Score model. See `buy_score_model.md` for how these get consumed, and `../ml/` for the concrete model implementations (XGBoost exit-price regressor, Random Survival Forest days-to-sell model, ResNet-50 reconditioning CNN, and the Buy Score combiner).
8. `market_event.schema.json` — detected disposition events (bankruptcy auctions, rental fleet refreshes, natural disasters, etc.) that explain *why* an asset is mispriced, not just what it is. `listing.source.market_event_ref` links a listing to the event driving its price.

`DATA_DICTIONARY.md` is auto-generated from all eight schemas above by `generate_data_dictionary.py` — re-run that script after any schema change; never hand-edit the dictionary itself, or it will drift out of sync with the schemas it's supposed to describe.

`listing.schema.json` also carries the vendor-enrichment extension points added for multi-source API ingestion (EquipmentWatch, Sandhills VIP+/FleetEvaluator, Rouse Services, USDA/EPA compliance): `verification.sources` (generic third-party verification, not one field per vendor), `asset.spec_attributes` (free-form category-specific specs — hydraulics flow, track width, undercarriage wear — that don't generalize across verticals), `location.compliance` (liens, title status, and an open `regulatory_flags` array for jurisdiction-specific requirements), and `comparables.provider_valuations` (raw third-party valuations kept distinct from Atlas's own blended regional_fmv/olv/flv). See `../ml/compliance_checklist.md` for the pre-acquisition legal gate these compliance fields back.

## How the records join

```
listing.asset.identity_ref ───────► asset_identity.identity_id
listing.record_id ◄──────────────── sold_transaction.listing_record_id
listing.source.market_event_ref ──► market_event.event_id
logistics_friction.listing_record_id ──► listing.record_id
training_labels.listing_record_id ──────► listing.record_id
training_labels.outcome_source.sold_transaction_id ──► sold_transaction.transaction_id
regional_demand keyed by (region, category, period) — no FK, queried directly
```

## Valuation basis mapping

`sold_transaction.sale.valuation_basis` and `listing.comparables` share one liquidation-value vocabulary. Typical (not hard-enforced) mapping by sale channel:

| Sale channel | `auction_type` | `valuation_basis` | Price elasticity |
|---|---|---|---|
| Unreserved auction | `unreserved` | `flv` (forced liquidation value) | Extremely high — same-day clearance |
| Reserved auction | `reserved` | `nflv` (net forced liquidation value) | Moderate |
| Retail dealer network | — | `olv` (orderly liquidation value) | Low — longer hold, profit-optimized |
| Wholesale / private | — | `nolv` (net orderly liquidation value) | Low to moderate |

`valuation_basis` is independently settable per record rather than derived, since real transactions have edge cases the mapping doesn't cover.

## Hours provenance

`listing.asset.hours` stays the single canonical hours value. `listing.asset.telematics.hours_source`/`hours_as_of` add *provenance* (seller-declared vs. OEM telematics API vs. estimated) rather than introducing a second competing hours field — avoid reading `telematics` fields as an alternate hours reading; they annotate the same number.

## `national_diesel_reference` vs. `fuel_price_usd_per_gallon`

Both live on `regional_demand.macro_signals` but answer different questions: `fuel_price_usd_per_gallon` is a regional retail price; `national_diesel_reference` is a national freight-industry benchmark (feeding `logistics_friction.transport.fuel_surcharge_pct`). Populate `national_diesel_reference` only on `region.level = "global"` rows — it's a national figure, and duplicating it across every metro/state row would just be redundant storage with no informational benefit.

## Point-in-time join contract

Every time-varying schema exposes an AS-OF timestamp field — the value that was *known*, not the period it *describes*. A point-in-time-correct join takes the latest row with `timestamp <= cutoff`, never a later one (see `../ml/point_in_time.py`):

| Schema | AS-OF field |
|---|---|
| `regional_demand` | `computed_at` |
| `logistics_friction` | `computed_at` |
| `listing.asset.telematics` | `reported_at` |
| `listing.source` | `scraped_at` |
| `sold_transaction.source` / `.sale` | `captured_at` / `sold_at` |

`period.end_date` on `regional_demand` is *not* an AS-OF field — a row can be backfilled well after its period ends, so training joins must cut off on `computed_at`, not `period.end_date`.

## Design decisions worth flagging

- **Raw vs. normalized fields stay separate everywhere a crawler writes.** `listing.raw` and `sold_transaction.source.raw` are unconstrained `additionalProperties: true` objects. Normalization bugs need to be replayable against the original payload without re-scraping.
- **`sold_transaction` vs. `training_labels` are not the same thing.** `sold_transaction` is market truth (any origin — auction result, dealer-reported, Atlas-facilitated) used to train/validate *valuation*. `training_labels` is specifically the (predicted Buy Score, realized outcome) pair used to train/validate the *Opportunity Engine*, and only the `atlas_facilitated` subset has real profit/ROI ground truth. Conflating them would let valuation-only comps quietly leak into Buy Score training as if they were profit outcomes.
- **`training_labels.prediction_snapshot` is frozen at prediction time**, not joined back to the live `listing` at training time — the live listing's price/status/comparables have moved on by the time a sale resolves, so joining back would leak future information into the training set.
- **`resolved_unsold` labels are kept, not discarded.** A `buy_now` recommendation that never sold at the predicted comp is a calibration signal.
- **Category is a lookup, not an inline enum**, because the category list grows every time Atlas launches a new vertical (construction today, aircraft/marine/medical tomorrow) and an inline enum means editing every schema file per launch.

## Open / not yet modeled

- Portfolio Intelligence, Autonomous Agent action logs, and Marketplace (escrow/insurance/financing) records aren't schematized yet — they consume these eight but weren't in the build order above.
- FX normalization (`sold_price` → `sold_price_usd`) assumes a daily-rate table that isn't schematized here.
- `listing.asset.telematics` is a point-in-time snapshot only. A full telematics *history* table (needed for real point-in-time joins against telemetry trends, not just latest-known-value) doesn't exist yet — deferred, not built.
- The full Tier 1–3 twenty-category taxonomy some strategy discussions raised (RVs, forklifts, mining/oil & gas equipment, etc.) is intentionally not built out — `priority_models.seed.json`'s narrow SKU list is the deliberate substitute while the platform focuses on one vertical.
- A dedicated Global Physical Asset Index schema doesn't exist — see PRD.md's Long-Term Vision section for why that's deferred.
