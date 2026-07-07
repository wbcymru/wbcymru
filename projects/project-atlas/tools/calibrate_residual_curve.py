"""Fits residual_value_curve.py's per-category constants against REAL sold
comps from the data store, replacing the illustrative placeholder params.

Reads data/sold_transactions.ndjson (populated via tools/atlas_data.py),
groups by asset.category, and fits (v0, k1, k2, k3) per category by
coarse-then-refined grid search minimizing squared error of
residual_value(hours) against sold price. Pure stdlib -- no numpy/scipy
in this environment, and at Phase 0 comp volumes a grid search is
entirely adequate.

Refuses to fit a category with fewer than MIN_COMPS usable records
(hours + USD price both present): a curve fit to a handful of points is
worse than the labeled placeholder, because it looks calibrated.

Output: data/calibration.json, consumed by tools/daily_report.py.

Buy Score constants (MIDPOINT/STEEPNESS in ml/buy_score.py) are NOT
refit here -- those need realized-profit ground truth from
atlas_facilitated training_labels, which only exist once real flips
have happened. This script covers valuation only.
"""

import argparse
import datetime
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "ml"))

from residual_value_curve import DepreciationCurveParams, residual_value  # noqa: E402

DEFAULT_DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MIN_COMPS = 20


def load_comps(data_dir: str) -> dict:
    """category -> list of (hours, price_usd)."""
    path = os.path.join(data_dir, "sold_transactions.ndjson")
    comps = {}
    if not os.path.exists(path):
        return comps
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            hours = r.get("asset", {}).get("hours")
            sale = r.get("sale", {})
            price = sale.get("sold_price_usd")
            if price is None and sale.get("currency") == "USD":
                price = sale.get("sold_price")
            if hours is None or price is None or price <= 0:
                continue
            comps.setdefault(r["asset"]["category"], []).append((float(hours), float(price)))
    return comps


def sse(points, params: DepreciationCurveParams) -> float:
    return sum((residual_value(h, params) - p) ** 2 for h, p in points)


def _grid(lo, hi, n):
    if n == 1:
        return [lo]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def fit_category(points) -> dict:
    """Coarse grid over (v0, k1, k2, k3), then one refinement pass around
    the best cell at half the step size."""
    max_price = max(p for _, p in points)
    max_hours = max(h for h, _ in points)

    v0_grid = _grid(max_price, 2.2 * max_price, 7)
    k1_grid = _grid(1e-5, 3e-4, 7)
    # keep the power term positive across observed hours: k2 < 1/max_hours
    k2_cap = 0.95 / max_hours if max_hours > 0 else 1.5e-4
    k2_grid = _grid(0.0, k2_cap, 6)
    k3_grid = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    best = None
    for v0 in v0_grid:
        for k1 in k1_grid:
            for k2 in k2_grid:
                for k3 in k3_grid:
                    params = DepreciationCurveParams(v0=v0, k1=k1, k2=k2, k3=k3)
                    err = sse(points, params)
                    if best is None or err < best[0]:
                        best = (err, params)

    # one refinement pass at half step around the winner
    _, b = best
    v0_step = (v0_grid[1] - v0_grid[0]) / 2
    k1_step = (k1_grid[1] - k1_grid[0]) / 2
    k2_step = (k2_grid[1] - k2_grid[0]) / 2 if len(k2_grid) > 1 else 0
    for v0 in _grid(max(b.v0 - v0_step, 1), b.v0 + v0_step, 5):
        for k1 in _grid(max(b.k1 - k1_step, 0), b.k1 + k1_step, 5):
            for k2 in _grid(max(b.k2 - k2_step, 0), min(b.k2 + k2_step, k2_cap), 5):
                for k3 in _grid(max(b.k3 - 0.25, 0.1), b.k3 + 0.25, 5):
                    params = DepreciationCurveParams(v0=v0, k1=k1, k2=k2, k3=k3)
                    err = sse(points, params)
                    if err < best[0]:
                        best = (err, params)

    err, params = best
    rmse = (err / len(points)) ** 0.5
    return {
        "v0": round(params.v0, 2),
        "k1": params.k1,
        "k2": params.k2,
        "k3": params.k3,
        "n_comps": len(points),
        "rmse_usd": round(rmse, 2),
        "fitted_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def cmd_fit(args):
    comps = load_comps(args.data_dir)
    if not comps:
        print(f"No sold comps found in {args.data_dir}/sold_transactions.ndjson -- "
              "add real records with tools/atlas_data.py first.")
        sys.exit(1)
    calibration, skipped = {}, []
    for category, points in sorted(comps.items()):
        if len(points) < MIN_COMPS:
            skipped.append((category, len(points)))
            continue
        result = fit_category(points)
        calibration[category] = result
        print(f"FITTED {category}: v0=${result['v0']:,.0f} k1={result['k1']:.2e} "
              f"k2={result['k2']:.2e} k3={result['k3']:.2f} "
              f"(n={result['n_comps']}, rmse=${result['rmse_usd']:,.0f})")
    for category, n in skipped:
        print(f"SKIPPED {category}: only {n} usable comps (< {MIN_COMPS} minimum) -- "
              "a curve fit to this little data would look calibrated without being trustworthy.")
    if calibration:
        out = os.path.join(args.data_dir, "calibration.json")
        with open(out, "w") as f:
            json.dump(calibration, f, indent=2)
        print(f"\nWrote {out}")
    else:
        print("\nNothing fitted; calibration.json not written.")
        sys.exit(1)


def cmd_self_test(args):
    """Synthesize comps from a known curve + deterministic noise, fit, and
    assert the fitted curve tracks the true curve within tolerance.
    Parameters themselves aren't asserted -- (v0, k1) trade off against
    each other, so identical-looking curves can have different params;
    what matters is predictive agreement."""
    true = DepreciationCurveParams(v0=60000, k1=5e-5, k2=8e-5, k3=1.5)
    points = []
    for i in range(40):
        hours = 100 + i * 150  # 100 .. 5950
        noise = 1.0 + 0.03 * (1 if i % 2 == 0 else -1) * ((i % 5) / 5.0)
        points.append((hours, residual_value(hours, true) * noise))

    result = fit_category(points)
    fitted = DepreciationCurveParams(v0=result["v0"], k1=result["k1"], k2=result["k2"], k3=result["k3"])

    errors = []
    for hours in range(200, 6000, 400):
        t = residual_value(hours, true)
        f = residual_value(hours, fitted)
        errors.append(abs(f - t) / t)
    mape = sum(errors) / len(errors)
    print(f"self-test: fitted curve vs true curve mean abs pct error = {mape:.1%} "
          f"(rmse on noisy points = ${result['rmse_usd']:,.0f})")
    assert mape < 0.10, f"fitted curve diverges from true curve by {mape:.1%} (>10%)"
    print("self-test passed: grid-search fit recovers the generating curve within 10%.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--self-test", action="store_true", help="run the synthetic-data fit test instead of fitting real comps")
    args = parser.parse_args()
    if args.self_test:
        cmd_self_test(args)
    else:
        cmd_fit(args)


if __name__ == "__main__":
    main()
