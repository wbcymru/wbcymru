"""Generates the "Top Buys" report as a single self-contained HTML file --
the Phase 0 deliverable people would eventually pay for, in its simplest
honest form.

Two modes:
  python3 tools/daily_report.py            # real listings from data/listings.ndjson
  python3 tools/daily_report.py --demo     # placeholder SAMPLE_LISTINGS, loudly labeled

Real mode scores each active listing through the same chain the
Opportunity Engine uses (residual curve -> freight -> recon -> Buy
Score), but every estimated input that isn't backed by real data or a
calibrated model is collected into a visible Assumptions section on the
report itself. The report never pretends an uncalibrated estimate is a
calibrated one -- that distinction is the whole difference between a
demo and a product someone should trust with money.
"""

import argparse
import datetime
import html
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "ml"))

from buy_score import OpportunityInputs, score_listing  # noqa: E402
from residual_value_curve import DepreciationCurveParams, residual_value  # noqa: E402
from opportunity_engine import CURVE_SHAPE, estimate_recon_cost  # noqa: E402

DEFAULT_DATA_DIR = os.path.join(PROJECT_ROOT, "data")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
PRIORITY_MODELS_PATH = os.path.join(PROJECT_ROOT, "schemas", "priority_models.seed.json")

# Assumption defaults used when a listing has no real value for the input.
# Each use is logged into the report's Assumptions section.
DEFAULT_FREIGHT_USD = 1500.0
DEFAULT_DAYS_TO_SELL = 30.0
CONFIDENCE_CALIBRATED = 0.85
CONFIDENCE_UNCALIBRATED = 0.50


def load_ndjson(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def load_calibration(data_dir):
    path = os.path.join(data_dir, "calibration.json")
    return json.load(open(path)) if os.path.exists(path) else {}


def load_priority_v0():
    """(manufacturer.lower(), model.lower()) -> top of typical price range,
    used as a rough v0 stand-in when no calibrated curve exists."""
    table = {}
    for m in json.load(open(PRIORITY_MODELS_PATH)):
        table[(m["manufacturer"].lower(), m["model"].lower())] = m["typical_price_range_usd"][1]
    return table


def acquisition_cost(listing, notes):
    p = listing.get("pricing", {})
    base = p.get("buy_now_price") or p.get("asking_price") or p.get("current_bid")
    if base is None:
        return None
    cost = float(base)
    if p.get("buyer_premium_pct"):
        cost += float(base) * p["buyer_premium_pct"] / 100.0
    if p.get("estimated_fees"):
        cost += p["estimated_fees"]
    if p.get("current_bid") and not p.get("buy_now_price") and not p.get("asking_price"):
        notes.add("Acquisition based on CURRENT BID -- final hammer price will likely be higher.")
    return cost


def score_real_listing(listing, calibration, priority_v0, assumptions):
    notes = set()
    asset = listing.get("asset", {})
    category = asset.get("category")
    hours = asset.get("hours")
    if hours is None:
        return None, "no hours recorded"
    acq = acquisition_cost(listing, notes)
    if acq is None:
        return None, "no price on listing"

    cal = calibration.get(category)
    if cal:
        params = DepreciationCurveParams(v0=cal["v0"], k1=cal["k1"], k2=cal["k2"], k3=cal["k3"])
        confidence = CONFIDENCE_CALIBRATED
        notes.add(f"Exit value from curve calibrated on {cal['n_comps']} real comps "
                  f"(rmse ${cal['rmse_usd']:,.0f}).")
    else:
        key = ((asset.get("manufacturer") or "").lower(), (asset.get("model") or "").lower())
        v0 = priority_v0.get(key)
        if v0 is None:
            return None, "no calibrated curve for category and model not in priority_models.seed.json"
        params = DepreciationCurveParams(v0=v0, **CURVE_SHAPE)
        confidence = CONFIDENCE_UNCALIBRATED
        notes.add("UNCALIBRATED exit value: placeholder curve shape with v0 from the "
                  "priority-model price range, NOT fitted to sold comps. Run "
                  "tools/calibrate_residual_curve.py once 20+ comps exist.")
    exit_value = residual_value(float(hours), params)

    friction = listing.get("friction") or {}
    freight = friction.get("estimated_transport_cost")
    if freight is None:
        freight = DEFAULT_FREIGHT_USD
        notes.add(f"Freight defaulted to ${DEFAULT_FREIGHT_USD:,.0f} (no quote on record).")
    recon = friction.get("estimated_repair_cost")
    if recon is None:
        recon = estimate_recon_cost(float(hours))
        notes.add("Recon from hours-based heuristic (no inspection on record).")

    days = DEFAULT_DAYS_TO_SELL
    notes.add(f"Days-to-sell defaulted to {DEFAULT_DAYS_TO_SELL:.0f} (no velocity model trained yet).")

    inputs = OpportunityInputs(
        acquisition_cost=acq, target_exit_value=exit_value,
        estimated_days_to_sell=days, estimated_freight_cost=float(freight),
        estimated_recon_cost=float(recon), confidence_score=confidence,
    )
    result = score_listing(inputs)
    loc = listing.get("location", {})
    result.update({
        "manufacturer": asset.get("manufacturer"), "model": asset.get("model"),
        "year": asset.get("year"), "hours": hours,
        "origin": ", ".join(x for x in [loc.get("city"), loc.get("state")] if x) or loc.get("country", ""),
        "acquisition_cost": acq,
        "url": listing.get("source", {}).get("url"),
        "why_mispriced": None,
    })
    assumptions.update(notes)
    return result, None


def render_html(rows, banner, assumptions, title):
    e = html.escape
    tr = []
    for rank, r in enumerate(rows, 1):
        machine = f"{r.get('year') or ''} {r['manufacturer']} {r['model']}".strip()
        link = f'<a href="{e(r["url"])}">source</a>' if r.get("url") else ""
        why = f'<div class="why">{e(r["why_mispriced"])}</div>' if r.get("why_mispriced") else ""
        tr.append(f"""<tr class="rec-{r['recommendation']}">
  <td>{rank}</td>
  <td>{e(machine)}{why}</td>
  <td>{e(str(r.get('origin') or ''))}</td>
  <td class="num">${r['acquisition_cost']:,.0f}</td>
  <td class="num">${r['expected_resale_value']:,.0f}</td>
  <td class="num">{r['roi_pct']:.1f}%</td>
  <td class="num">{r['expected_days_to_sell']:.0f}</td>
  <td class="num">{r['confidence_score']:.2f}</td>
  <td class="num score">{r['buy_score']}</td>
  <td class="rec">{e(r['recommendation'].replace('_', ' ').upper())}</td>
  <td>{link}</td>
</tr>""")
    assumption_items = "\n".join(f"<li>{e(a)}</li>" for a in sorted(assumptions))
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>
  body {{ font: 15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; color: #1a1a1a; background: #fafafa; margin: 0; padding: 2rem 1rem; }}
  main {{ max-width: 68rem; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 .25rem; }}
  .sub {{ color: #666; margin: 0 0 1.25rem; }}
  .banner {{ background: #fff3cd; border: 1px solid #e0c96a; border-radius: 6px; padding: .75rem 1rem; margin-bottom: 1.25rem; font-weight: 600; }}
  .table-wrap {{ overflow-x: auto; background: #fff; border: 1px solid #e2e2e2; border-radius: 8px; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 56rem; }}
  th, td {{ padding: .55rem .7rem; text-align: left; border-bottom: 1px solid #eee; vertical-align: top; }}
  th {{ font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; color: #555; background: #f4f4f4; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.score {{ font-weight: 700; }}
  tr.rec-buy_now td.rec {{ color: #106b21; font-weight: 700; }}
  tr.rec-watch td.rec {{ color: #8a6d00; font-weight: 600; }}
  tr.rec-pass td.rec {{ color: #999; }}
  .why {{ color: #777; font-size: .82rem; }}
  section.assumptions {{ margin-top: 1.5rem; background: #fff; border: 1px solid #e2e2e2; border-radius: 8px; padding: 1rem 1.25rem; }}
  section.assumptions h2 {{ font-size: 1rem; margin: 0 0 .5rem; }}
  section.assumptions li {{ margin: .2rem 0; color: #444; }}
  footer {{ margin-top: 1rem; color: #999; font-size: .8rem; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #131313; color: #e8e8e8; }}
    .table-wrap, section.assumptions {{ background: #1c1c1c; border-color: #333; }}
    th {{ background: #222; color: #aaa; }}
    th, td {{ border-color: #2c2c2c; }}
    .banner {{ background: #3a3110; border-color: #6b5c1e; color: #f0dc8c; }}
    .why {{ color: #999; }}
    section.assumptions li {{ color: #bbb; }}
    tr.rec-buy_now td.rec {{ color: #57c46a; }}
    tr.rec-watch td.rec {{ color: #d9b23a; }}
    a {{ color: #7ab8f5; }}
  }}
</style>
<main>
<h1>{e(title)}</h1>
<p class="sub">Project Atlas — Opportunity Engine output, generated {generated}</p>
{f'<div class="banner">{e(banner)}</div>' if banner else ''}
<div class="table-wrap">
<table>
<thead><tr><th>#</th><th>Machine</th><th>Location</th><th>Acq $</th><th>Exit $</th><th>ROI</th><th>Days</th><th>Conf</th><th>Buy Score</th><th>Rec</th><th></th></tr></thead>
<tbody>
{"".join(tr)}
</tbody>
</table>
</div>
<section class="assumptions">
<h2>Assumptions &amp; data caveats</h2>
<ul>
{assumption_items}
</ul>
</section>
<footer>Generated by tools/daily_report.py. Buy Score constants are calibrated against a worked example, not live outcomes — see schemas/buy_score_model.md.</footer>
</main>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--demo", action="store_true", help="render placeholder SAMPLE_LISTINGS instead of the real data store")
    parser.add_argument("-n", "--top", type=int, default=10)
    parser.add_argument("-o", "--output", help="output path (default: reports/top_buys_<date|demo>.html)")
    args = parser.parse_args()

    assumptions = set()
    if args.demo:
        from opportunity_engine import top_buys
        rows = top_buys(args.top)
        banner = ("DEMO — PLACEHOLDER DATA. Every listing on this page is fictional sample data. "
                  "Nothing here is a real machine or a real recommendation.")
        title = "Top Buys — DEMO (placeholder data)"
        assumptions.add("All listings are hand-written illustrative samples; no live data source is connected.")
        default_name = "top_buys_demo.html"
    else:
        listings = [l for l in load_ndjson(os.path.join(args.data_dir, "listings.ndjson"))
                    if l.get("source", {}).get("status") == "active"]
        if not listings:
            print(f"No active listings in {args.data_dir}/listings.ndjson.")
            print("Add real records with tools/atlas_data.py, or run with --demo to see the format.")
            sys.exit(1)
        calibration = load_calibration(args.data_dir)
        priority_v0 = load_priority_v0()
        rows, skipped = [], []
        for listing in listings:
            result, reason = score_real_listing(listing, calibration, priority_v0, assumptions)
            if result:
                rows.append(result)
            else:
                skipped.append((listing["record_id"][:8], reason))
        for rid, reason in skipped:
            print(f"skipped {rid}: {reason}")
        if not rows:
            print("No scorable listings (see skips above).")
            sys.exit(1)
        rows.sort(key=lambda r: r["buy_score"], reverse=True)
        rows = rows[: args.top]
        n_cal = len(calibration)
        banner = None if n_cal else ("UNCALIBRATED ESTIMATES — real listings, but exit values come from a "
                                     "placeholder depreciation curve not yet fitted to sold comps. "
                                     "Directionally useful at best; do not size purchases off these numbers.")
        title = f"Top Buys — {datetime.date.today().isoformat()}"
        default_name = f"top_buys_{datetime.date.today().isoformat()}.html"

    os.makedirs(REPORTS_DIR, exist_ok=True)
    out = args.output or os.path.join(REPORTS_DIR, default_name)
    with open(out, "w") as f:
        f.write(render_html(rows, banner, assumptions, title))
    print(f"Report written to {out} ({len(rows)} opportunities)")


if __name__ == "__main__":
    main()
