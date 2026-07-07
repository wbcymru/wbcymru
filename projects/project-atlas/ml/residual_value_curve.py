"""Non-linear residual-value depreciation curve, driven by cumulative hours
rather than calendar age.

V(hours) = V0 * exp(-k1*hours) * max(0, 1 - k2*hours)**k3, floored at a
scrap-value percentage of V0.

This is an interpretable FALLBACK PRIOR / baseline for expected resale
value -- useful when a category/region has too few sold_transaction comps
for Model I (exit_price_model.py) to fit reliably, and useful as a sanity
check on Model I's output elsewhere. It is not a replacement for Model I,
which already learns an hours-value relationship implicitly from real
sold_transaction data; the two should not silently diverge (see the
cross-reference note in exit_price_model.py and schemas/buy_score_model.md).

CAVEAT: the functional form and all constants below are illustrative
placeholders, not fit to real data. Calibrate v0/k1/k2/k3 per category
against actual sold_transaction records before trusting this at any real
capital scale.
"""

from dataclasses import dataclass


@dataclass
class DepreciationCurveParams:
    v0: float                 # new/reference value, hours=0
    k1: float                 # exponential decay rate
    k2: float                 # power-decay rate (1/k2 ~ hours at which the power term hits zero)
    k3: float                 # power-decay exponent (curve sharpness near end of life)
    scrap_value_pct: float = 0.05  # floor, as a fraction of v0


def residual_value(hours: float, params: DepreciationCurveParams) -> float:
    if hours < 0:
        raise ValueError("hours must be non-negative")
    import math

    exponential_term = math.exp(-params.k1 * hours)
    power_term = max(0.0, 1 - params.k2 * hours) ** params.k3
    value = params.v0 * exponential_term * power_term
    floor = params.v0 * params.scrap_value_pct
    return max(value, floor)


if __name__ == "__main__":
    # Illustrative compact-track-loader curve: $55k new, gentle early decay,
    # steeper falloff approaching a ~10,000-hour service life.
    ctl_params = DepreciationCurveParams(v0=55000, k1=0.00004, k2=0.00009, k3=1.5)
    for hours in (0, 500, 1500, 3000, 6000, 9000, 11000):
        print(f"{hours:>6} hrs -> ${residual_value(hours, ctl_params):,.0f}")
