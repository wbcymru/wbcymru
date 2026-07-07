# Project Atlas — Data Schemas

Raw data schema first, ML model downstream. Bad schema = bad model. Build/review order:

1. `taxonomy.schema.json` + `categories.seed.json` — controlled vocabulary every `category` field draws from.
2. `listing.schema.json` — normalized record for one observed listing. Raw source payload preserved verbatim under `raw`, normalized fields alongside it. Never overwrite `raw`.
3. `sold_transaction.schema.json` — ground truth. Listings are signals; sold transactions are labels.
4. `asset_identity.schema.json` — VIN/serial/UDI/tail-number decode, so the same physical unit can be tracked across multiple listings and resales over its lifetime.
5. `logistics_friction.schema.json` — transport, repair, cleaning, tax, fees. Source of truth for the `friction` block that `listing` denormalizes a snapshot of.
6. `regional_demand.schema.json` — (region, category, period) supply/demand/macro feature table for the Market Intelligence Engine.
7. `training_labels.schema.json` — frozen (prediction, outcome) pairs for the Buy Score model. See `buy_score_model.md` for how these get consumed.

## How the records join

```
listing.asset.identity_ref ───────► asset_identity.identity_id
listing.record_id ◄──────────────── sold_transaction.listing_record_id
logistics_friction.listing_record_id ──► listing.record_id
training_labels.listing_record_id ──────► listing.record_id
training_labels.outcome_source.sold_transaction_id ──► sold_transaction.transaction_id
regional_demand keyed by (region, category, period) — no FK, queried directly
```

## Design decisions worth flagging

- **Raw vs. normalized fields stay separate everywhere a crawler writes.** `listing.raw` and `sold_transaction.source.raw` are unconstrained `additionalProperties: true` objects. Normalization bugs need to be replayable against the original payload without re-scraping.
- **`sold_transaction` vs. `training_labels` are not the same thing.** `sold_transaction` is market truth (any origin — auction result, dealer-reported, Atlas-facilitated) used to train/validate *valuation*. `training_labels` is specifically the (predicted Buy Score, realized outcome) pair used to train/validate the *Opportunity Engine*, and only the `atlas_facilitated` subset has real profit/ROI ground truth. Conflating them would let valuation-only comps quietly leak into Buy Score training as if they were profit outcomes.
- **`training_labels.prediction_snapshot` is frozen at prediction time**, not joined back to the live `listing` at training time — the live listing's price/status/comparables have moved on by the time a sale resolves, so joining back would leak future information into the training set.
- **`resolved_unsold` labels are kept, not discarded.** A `buy_now` recommendation that never sold at the predicted comp is a calibration signal.
- **Category is a lookup, not an inline enum**, because the category list grows every time Atlas launches a new vertical (construction today, aircraft/marine/medical tomorrow) and an inline enum means editing every schema file per launch.

## Open / not yet modeled

- Portfolio Intelligence, Autonomous Agent action logs, and Marketplace (escrow/insurance/financing) records aren't schematized yet — they consume these seven but weren't in the build order above.
- FX normalization (`sold_price` → `sold_price_usd`) assumes a daily-rate table that isn't schematized here.
