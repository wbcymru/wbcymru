# Buy Score Model — Spec

Downstream consumer of every schema in this directory. Not a data record itself — this documents the model that reads them, so schema changes upstream have one place to check for breakage.

## Objective

Given a `listing` record (plus everything it can be joined to), output the `scoring` block: `buy_score`, `recommendation`, `expected_resale_value`, `expected_days_to_sell`, `net_expected_profit`, `roi_pct`, `confidence_score`.

## Inputs (feature sources)

| Source | Schema | Contributes |
|---|---|---|
| Listing under evaluation | `listing.schema.json` | asset condition, current pricing, auction dynamics |
| Decoded identity | `asset_identity.schema.json` | trustworthy year/model/options, resolves listing ambiguity |
| Comparable sales | `sold_transaction.schema.json` | regional FMV/OLV/FLV inputs, price trend basis |
| Cost to realize | `logistics_friction.schema.json` | net profit = resale − acquisition − friction |
| Market context | `regional_demand.schema.json` | demand/supply forecast, seasonality, macro adjustment |

## Model family (by sub-task)

- **Valuation** (expected_resale_value, regional_fmv/olv/flv): gradient-boosted trees over structured features (asset attributes, condition score, regional pricing signals) — not deep learning; tabular data with strong monotonic priors (more hours = lower value) favors GBTs for both accuracy and explainability to end users who need to trust a number before spending money.
- **Days-to-sell**: time-series / survival model over `regional_demand` history for the category+region, adjusted by listing-specific condition and price-vs-comp positioning.
- **Buy Score / recommendation**: a calibrated combination of (predicted ROI, confidence, days-to-sell, capital efficiency) into a single 0–100 score and a `buy_now | watch | pass` cutoff. Reinforcement learning is scoped to *execution* (bid timing, negotiation) per the PRD, not to the underlying Buy Score itself, which needs to stay a supervised, auditable model — an investor acting on it has to be able to ask "why" and get a features-and-weights answer, not a policy black box.

## Training

Labels come exclusively from `training_labels.schema.json`. Two label populations, kept distinct:

1. **Valuation labels** — any `sold_transaction` (any `origin`), used to train/validate expected_resale_value and regional_fmv/olv/flv. High volume, lower trust per-record.
2. **Buy Score labels** — only `training_labels` rows with `outcome_source.origin = atlas_facilitated`, since only those have real `actual_net_profit`/`actual_roi_pct`. Low volume early on; this population grows only as fast as Atlas actually transacts, which is why cold-start Buy Score should initially be a rules-derived heuristic (spread vs. comps, adjusted for friction) rather than a trained model, and only cut over once `resolved_sold` atlas_facilitated labels reach enough volume per category to fit reliably.

`resolved_unsold` labels matter as much as `resolved_sold` ones — a `buy_now` recommendation that never sold at the predicted comp is a miscalibration signal, not a data gap to discard.

## Non-goals for v1

- No per-user personalization of Buy Score (same asset scores the same for every user; portfolio fit is a separate downstream filter, not baked into the score).
- No live reinforcement-learning bidding loop until there's enough `atlas_facilitated` transaction volume to make off-policy evaluation trustworthy.
