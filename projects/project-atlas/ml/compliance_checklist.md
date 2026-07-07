# Pre-Acquisition Compliance Checklist

Gate before transport is booked on any cross-border acquisition. Backed by `listing.location.compliance` in `../schemas/listing.schema.json` — each item below maps to a schema field so the gate is queryable, not just documented.

| # | Check | Why | Schema field |
|---|---|---|---|
| 1 | **Lien clearance & title verification** — run serial number against state/registry lien databases before transport | A flagged security interest gets the asset seized at the U.S. border; there is no partial-transport fallback | `location.compliance.has_active_liens` must resolve to `false` |
| 2 | **72-hour title stamp** — physical title submitted to CBP at least 72 hours before land crossing or port loading | Missing this window causes border delays that blow the estimated_days_to_sell assumption the Buy Score was computed against | `location.compliance.title_in_hand`, `regulatory_flags` entry with `flag: "cbp_title_stamp_72h"` |
| 3 | **EPA Clean Air compliance** — verify Tier 4 diesel engine labels intact, file EPA Form 3520-21 | Cross-border diesel equipment without this clears customs slower or not at all | `regulatory_flags` entry with `flag: "epa_tier4_compliance"` |

Category-specific flags (not universal, hence modeled as the open `regulatory_flags` array rather than named schema fields):

- `usda_cleanliness_inspection` — biological/soil cleaning required for agricultural equipment crossing certain borders
- `escort_vehicle_required` — oversize-load requirement for cranes/large construction equipment

All flags in `regulatory_flags` must have `satisfied: true` before `logistics_friction` transport booking proceeds — an unresolved `required: true` flag should block the Opportunity Engine from surfacing a `buy_now` recommendation regardless of Buy Score.
