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

Concrete implementations live in `../ml/`.

- **Model I — Expected Regional Exit Price** (`ml/models/exit_price_model.py`): XGBoost regressor, RMSE + L2 objective. Not deep learning; tabular data with strong monotonic priors (more hours = lower value) favors GBTs for both accuracy and the explainability an investor needs before spending money, and RMSE+L2 resists overfitting on the sparse regional/category training slices this data actually has. A candidate future bake-off: Extra Trees Regressor and other ensemble variants have been suggested as potentially higher-accuracy alternatives — worth evaluating once real labeled volume exists, but **do not swap the primary model based on unsourced comparison figures**; any accuracy claims for alternatives need to be verified against this project's own held-out data before they inform a model choice. `ml/residual_value_curve.py` provides an interpretable hours-driven depreciation-curve *prior*, useful as a sparse-data fallback and a sanity check on this model's output — the two should not silently diverge; if the curve and the trained model disagree materially for a category, that's a signal to investigate, not just take the model's number.
- **Point-in-time correctness**: all training feature joins for Model I (and Model II) — regional_demand signals, telematics history — must go through `ml/point_in_time.py`'s AS-OF join utilities, not a naive join to the current/live state of those tables. This generalizes the same leakage-prevention rationale already applied to `training_labels.prediction_snapshot` (frozen at prediction time) to every joined time-varying feature.
- **Model II — Predicted Days to Sell** (`ml/models/days_to_sell_model.py`): Random Survival Forest, not a plain regressor — active unsold listings are *censored* observations ("at least N days, sale unknown"), not missing data, and a plain regressor trained only on resolved sales would silently drop them and bias toward fast-sellers. Evaluated on Harrell's C-index rather than MAE, since censored rows have no true days-to-sell to score against.
- **Model III — Image-Based Reconditioning Estimator** (`ml/models/condition_cnn.py`): fine-tuned dual-head ResNet-50 over listing photos (mechanical wear + cosmetic condition heads sharing one backbone), output mapped through a repair-cost lookup matrix into `logistics_friction.repair.line_items` with `assessment_source: vision_ai`.
- **Buy Score / recommendation** (`ml/buy_score.py`): combines Models I–III plus friction into net profit, annualizes ROI by estimated hold time (capital velocity — a lower-margin deal that clears in 20 days can beat a higher-margin deal tying up capital for 90), weights by confidence, and squashes through a logistic into 0–100 with `buy_now | watch | pass` cutoffs at 85/65. This is the same shape as `B_s = sigmoid(pricing_discrepancy_variable)` — `pricing_discrepancy_variable` is `confidence_score * annualized_roi` in the current implementation. Reinforcement learning is scoped to *execution* (bid timing, negotiation) per the PRD, not to the Buy Score itself, which needs to stay a supervised, auditable function — an investor acting on it has to be able to ask "why" and get a features-and-weights answer, not a policy black box.
- **`ml/opportunity_engine.py`** runs this whole chain end-to-end (residual value curve as valuation prior, transport cost, buy_score) against a small placeholder sample dataset — the "Top N Buys" report — as a working demonstration of the mechanism. It is explicitly not connected to a live data source.

## Training

Labels come exclusively from `training_labels.schema.json`. Two label populations, kept distinct:

1. **Valuation labels** — any `sold_transaction` (any `origin`), used to train/validate expected_resale_value and regional_fmv/olv/flv. High volume, lower trust per-record.
2. **Buy Score labels** — only `training_labels` rows with `outcome_source.origin = atlas_facilitated`, since only those have real `actual_net_profit`/`actual_roi_pct`. Low volume early on; this population grows only as fast as Atlas actually transacts, which is why v1 Buy Score is the calibrated closed-form heuristic in `ml/buy_score.py` rather than a trained model, and only cuts over once `resolved_sold` atlas_facilitated labels reach enough volume per category to fit reliably. The heuristic's constants (`MIDPOINT`, `STEEPNESS`) were back-solved to match a worked example, not learned — refit them against real outcomes before trusting the score at any real capital scale.

`resolved_unsold` labels matter as much as `resolved_sold` ones — a `buy_now` recommendation that never sold at the predicted comp is a miscalibration signal, not a data gap to discard.

## Non-goals for v1

- No per-user personalization of Buy Score (same asset scores the same for every user; portfolio fit is a separate downstream filter, not baked into the score).
- No live reinforcement-learning bidding loop until there's enough `atlas_facilitated` transaction volume to make off-policy evaluation trustworthy.
