"""Opportunity Engine v0.1 -- the "Top N Buys" report.

*** USES PLACEHOLDER DATA, NOT A LIVE FEED ***
SAMPLE_LISTINGS below is a small, hand-built, illustrative dataset covering
the Phase-2 priority vertical (compact track loaders / skid steers from
Bobcat, CAT, Deere, Kubota, Takeuchi -- see priority_models.seed.json).
There is no scraper, auction API, or dealer feed connected in this
environment. This module exists to demonstrate the scoring mechanism
end-to-end, not to report real market opportunities. Replace
SAMPLE_LISTINGS with real listing.schema.json records (joined through
logistics_friction/regional_demand) before treating any output as a real
recommendation.

Pipeline per listing: residual_value_curve.py estimates target exit value
from hours (a fallback prior, standing in for a trained Model I),
transport_cost.py estimates freight, a simple hours-based heuristic
estimates recon cost, and buy_score.py turns all of that into a ranked
Buy Score / recommendation -- the same shape as listing.scoring.
"""

from dataclasses import dataclass

from buy_score import OpportunityInputs, score_listing
from residual_value_curve import DepreciationCurveParams, residual_value
from transport_cost import TransportCostInputs, total_transport_cost

# Generic compact-track-loader/skid-steer depreciation curve (illustrative --
# see residual_value_curve.py's calibration caveat). v0 is per-listing
# (approx new/replacement price), shape params shared across this narrow
# vertical since these machines wear similarly.
CURVE_SHAPE = {"k1": 0.00004, "k2": 0.00009, "k3": 1.5}


@dataclass
class SampleListing:
    manufacturer: str
    model: str
    replacement_value_usd: float  # v0 for the depreciation curve, approx new price
    hours: float
    acquisition_cost: float
    origin: str
    distance_to_resale_hub_miles: float
    freight_rate_per_mile: float
    confidence: float
    estimated_days_to_sell: float
    why_mispriced: str


# *** PLACEHOLDER DATA -- see module docstring. Not live listings. ***
SAMPLE_LISTINGS = [
    SampleListing("Kubota", "SVL75", 62000, 900, 34500, "Dallas, TX", 1550, 2.05, 0.94, 20, "Dealer aging inventory, 200+ days on lot"),
    SampleListing("Bobcat", "T76", 68000, 1400, 39000, "Phoenix, AZ", 1100, 1.95, 0.90, 25, "Rental fleet refresh, off-lease unit"),
    SampleListing("CAT", "259D3", 74000, 2600, 41000, "Orlando, FL", 900, 2.10, 0.85, 30, "Bankruptcy auction, unreserved"),
    SampleListing("Deere", "317G", 70000, 1800, 44500, "Denver, CO", 700, 2.00, 0.88, 28, "Municipal surplus"),
    SampleListing("Takeuchi", "TL12", 69000, 3200, 40000, "Charlotte, NC", 600, 1.90, 0.80, 35, "Estate sale"),
    SampleListing("Bobcat", "S650", 55000, 600, 33000, "Kansas City, MO", 800, 1.85, 0.93, 18, "Manufacturer rebate pushed trade-ins to market"),
    SampleListing("Kubota", "SVL97", 78000, 4200, 47000, "Boise, ID", 1300, 2.15, 0.72, 45, "Farm retirement, worn undercarriage suspected"),
    SampleListing("CAT", "289D3", 82000, 3800, 61000, "Seattle, WA", 1600, 2.20, 0.68, 50, "Wholesale/private, thin margin"),
    SampleListing("Deere", "325G", 76000, 2200, 52000, "Atlanta, GA", 500, 1.95, 0.82, 32, "Construction slowdown regional oversupply"),
    SampleListing("Takeuchi", "TL10", 62000, 1600, 37500, "Nashville, TN", 450, 1.90, 0.91, 22, "Insurance write-off, cosmetic only per inspection"),
    SampleListing("Bobcat", "S76", 60000, 2800, 41000, "Sacramento, CA", 1400, 2.25, 0.60, 55, "Government liquidation, high hours"),
    SampleListing("CAT", "259D3", 74000, 900, 52000, "Chicago, IL", 950, 2.05, 0.70, 40, "Retail-priced, minimal spread"),
]

RECON_COST_PER_1000_HOURS_OVER_3000 = 400  # illustrative wear-based recon estimate


def estimate_recon_cost(hours: float) -> float:
    worn_hours = max(0.0, hours - 3000)
    return (worn_hours / 1000.0) * RECON_COST_PER_1000_HOURS_OVER_3000


def score_sample_listing(listing: SampleListing) -> dict:
    curve_params = DepreciationCurveParams(v0=listing.replacement_value_usd, **CURVE_SHAPE)
    target_exit_value = residual_value(listing.hours, curve_params)

    freight = total_transport_cost(TransportCostInputs(
        distance_miles=listing.distance_to_resale_hub_miles,
        rate_per_mile=listing.freight_rate_per_mile,
        fuel_surcharge_pct=12.0,
    ))
    recon = estimate_recon_cost(listing.hours)

    inputs = OpportunityInputs(
        acquisition_cost=listing.acquisition_cost,
        target_exit_value=target_exit_value,
        estimated_days_to_sell=listing.estimated_days_to_sell,
        estimated_freight_cost=freight,
        estimated_recon_cost=recon,
        confidence_score=listing.confidence,
    )
    result = score_listing(inputs)
    result["manufacturer"] = listing.manufacturer
    result["model"] = listing.model
    result["origin"] = listing.origin
    result["acquisition_cost"] = listing.acquisition_cost
    result["why_mispriced"] = listing.why_mispriced
    return result


def top_buys(n: int = 10):
    scored = [score_sample_listing(listing) for listing in SAMPLE_LISTINGS]
    scored.sort(key=lambda r: r["buy_score"], reverse=True)
    return scored[:n]


def print_report(n: int = 10):
    print("=" * 100)
    print("OPPORTUNITY ENGINE v0.1 -- Top Buys (compact track loader / skid steer vertical)")
    print("*** PLACEHOLDER DATA -- illustrative sample listings, not a live feed ***")
    print("=" * 100)
    header = f"{'#':<3}{'Machine':<22}{'Origin':<18}{'Buy':<9}{'Acq $':<10}{'Exit $':<10}{'ROI %':<8}{'Days':<6}{'Conf':<6}{'Rec':<9}"
    print(header)
    print("-" * 100)
    for rank, r in enumerate(top_buys(n), start=1):
        machine = f"{r['manufacturer']} {r['model']}"
        print(
            f"{rank:<3}{machine:<22}{r['origin']:<18}{r['buy_score']:<9}"
            f"{r['acquisition_cost']:<10,.0f}{r['expected_resale_value']:<10,.0f}"
            f"{r['roi_pct']:<8.1f}{r['expected_days_to_sell']:<6.0f}{r['confidence_score']:<6.2f}{r['recommendation']:<9}"
        )
        print(f"      why: {r['why_mispriced']}")
    print("-" * 100)


if __name__ == "__main__":
    print_report(10)
