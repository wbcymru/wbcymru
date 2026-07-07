"""Combines Model I/II/III outputs plus friction into the Buy Score (B_s).

listing.scoring is always model-derived (see schemas/listing.schema.json);
this module is what actually populates it. Per buy_score_model.md, Buy
Score starts as this calibrated heuristic rather than a trained model,
because atlas_facilitated training_labels volume is too low early on to
fit one reliably — this function *is* the v1 model, and gets replaced by
a learned one once enough resolved_sold atlas_facilitated labels exist
per category.
"""

import math
from dataclasses import dataclass

# Back-solved from the two-listing worked example in the PRD's "Trading
# Terminal" mockup (Kubota BX23S -> 97.8/BUY NOW, Cat 259D3 -> 62.4/PASS).
# Treat as an initial calibration, not a derived constant — refit MIDPOINT
# and STEEPNESS against real atlas_facilitated outcomes as they accumulate.
MIDPOINT = 0.531   # confidence-weighted annualized ROI at which score = 50
STEEPNESS = 1.454

BUY_NOW_THRESHOLD = 85.0
WATCH_THRESHOLD = 65.0


@dataclass
class OpportunityInputs:
    acquisition_cost: float
    target_exit_value: float          # Model I output
    estimated_days_to_sell: float      # Model II output
    estimated_freight_cost: float
    estimated_recon_cost: float        # sum of Model III line_items
    confidence_score: float            # 0-1, blended from model uncertainty


def net_expected_profit(i: OpportunityInputs) -> float:
    return i.target_exit_value - i.acquisition_cost - i.estimated_freight_cost - i.estimated_recon_cost


def cost_basis(i: OpportunityInputs) -> float:
    return i.acquisition_cost + i.estimated_freight_cost + i.estimated_recon_cost


def roi_pct(i: OpportunityInputs) -> float:
    basis = cost_basis(i)
    return net_expected_profit(i) / basis if basis else 0.0


def annualized_roi(i: OpportunityInputs) -> float:
    """ROI adjusted for capital velocity — a lower-margin deal that clears
    in 20 days can beat a higher-margin deal that ties up capital for 90."""
    days = max(i.estimated_days_to_sell, 1.0)
    return roi_pct(i) * (365.0 / days)


def buy_score(i: OpportunityInputs) -> float:
    """0-100. Logistic squash of confidence-weighted annualized ROI, so
    score saturates instead of blowing up on very fast/high-margin flips
    and stays sensitive in the mid-range where buy/pass calls are close."""
    x = i.confidence_score * annualized_roi(i)
    return 100.0 / (1.0 + math.exp(-STEEPNESS * (x - MIDPOINT)))


def recommendation(score: float) -> str:
    if score >= BUY_NOW_THRESHOLD:
        return "buy_now"
    if score >= WATCH_THRESHOLD:
        return "watch"
    return "pass"


def score_listing(i: OpportunityInputs) -> dict:
    """Shape matches listing.scoring in schemas/listing.schema.json."""
    s = buy_score(i)
    return {
        "expected_resale_value": i.target_exit_value,
        "expected_days_to_sell": i.estimated_days_to_sell,
        "gross_spread": i.target_exit_value - i.acquisition_cost,
        "net_expected_profit": net_expected_profit(i),
        "roi_pct": roi_pct(i) * 100.0,
        "confidence_score": i.confidence_score,
        "buy_score": round(s, 1),
        "recommendation": recommendation(s),
    }


if __name__ == "__main__":
    kubota = OpportunityInputs(14700, 19400, 22, 900, 600, 0.96)
    cat = OpportunityInputs(34000, 44200, 41, 2800, 2200, 0.74)
    for name, opp in [("Kubota BX23S", kubota), ("Cat 259D3", cat)]:
        print(name, score_listing(opp))
