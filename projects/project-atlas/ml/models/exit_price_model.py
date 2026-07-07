"""Model I: Expected Regional Exit Price (V_target).

Gradient-boosted tree regressor predicting the retail clearing price an
asset will fetch in a target zip code. Trained exclusively on
sold_transaction records (see ../../schemas/sold_transaction.schema.json)
labeled per ../../schemas/training_labels.schema.json — active listings
are signals, sold transactions are the label.
"""

import xgboost as xgb

# Feature columns pulled from the schemas, joined at training time:
#   listing.asset: manufacturer, model, year, hours
#   listing.location: postal_code -> target zip's regional_demand cell
#   regional_demand.supply_signals / demand_signals / macro_signals
#   regional_demand.pricing_signals: avg_sold_price, price_trend_pct_30d/90d
#   listing.comparables.provider_valuations: Rouse / Sandhills / EquipmentWatch
#     regional transactional data, used as features, not the label
FEATURE_COLUMNS = [
    "standardized_manufacturer",
    "standardized_model",
    "standardized_year",
    "engine_hours",
    "construction_starts_index_30d",
    "housing_permits_index_30d",
    "dealer_density_oem",
    "sandhills_regional_avg",
    "rouse_regional_avg",
]

TARGET_COLUMN = "actual_sold_price"  # sold_transaction.sale.sold_price_usd


def build_model() -> xgb.XGBRegressor:
    """Construct the exit-price regressor.

    Objective is plain squared-error RMSE with L2 (reg_lambda) regularization
    rather than a more exotic loss, because regional training slices are
    sparse (a single zip/category/year cell may have only a handful of sold
    comps) and RMSE + L2 is the combination least likely to overfit that.
    """
    return xgb.XGBRegressor(
        n_estimators=1500,
        max_depth=7,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.5,
        objective="reg:squarederror",
        random_state=42,
    )


exit_price_model = build_model()
