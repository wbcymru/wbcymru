"""Model II: Predicted Days to Sell (T_est).

Random Survival Forest rather than a plain regressor, specifically because
listings that are still active and unsold are *censored* observations, not
missing data — a skid steer listed 90 days ago with no sale yet tells the
model "at least 90 days," not "unknown." A standard regressor trained only
on resolved sales would silently drop those and bias toward fast-selling
assets.
"""

from sksurv.ensemble import RandomSurvivalForest

# Feature columns:
#   regional_demand.demand_signals / macro_signals (seasonality, fuel price,
#     rainfall deviation) for the listing's category + target region
#   listing.pricing vs regional_demand.pricing_signals.median_sold_price
#     -> price-to-market ratio
#   sold_transaction.sale.days_on_market for correlated category/region,
#     as historical basis
FEATURE_COLUMNS = [
    "seasonal_demand_multiplier",
    "price_to_market_ratio",
    "regional_time_on_market_baseline",
    "diesel_price_avg",
    "rainfall_deviation_index",
]

# Structured target array per scikit-survival convention:
#   event: True if sold (label_status = resolved_sold), False if censored
#     (label_status = pending / resolved_unsold at time of training cutoff)
#   time:  training_labels.ground_truth.actual_days_to_sell, or days observed
#          so far for censored (unsold) listings
TARGET_EVENT_FIELD = "sold"
TARGET_TIME_FIELD = "days_observed"


def build_model() -> RandomSurvivalForest:
    """Construct the days-to-sell survival model.

    Evaluated via Harrell's concordance index (C-index) — the probability
    that, for two randomly chosen listings, the one predicted to sell
    faster actually does — rather than MAE/RMSE on days, since censored
    listings don't have a true "days to sell" value to score against.
    """
    return RandomSurvivalForest(
        n_estimators=500,
        min_samples_split=10,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )


days_to_sell_model = build_model()
