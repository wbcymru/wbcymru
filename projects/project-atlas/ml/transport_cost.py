"""Heavy-haul transport cost estimator.

Implements logistics_friction.transport as a formula rather than requiring
a live carrier quote for every listing: total_cost = linehaul (rate per
mile x distance, scaled by fuel surcharge) plus permitting, escort, and
assembly/disassembly line items.

ASSUMPTION: fuel_surcharge_pct applies multiplicatively to linehaul only,
not to permit/escort/assembly costs -- this is the standard DAT Freight
Rate convention, but is a modeling choice worth flagging, not a law of
physics.
"""

from dataclasses import dataclass


@dataclass
class TransportCostInputs:
    distance_miles: float
    rate_per_mile: float          # e.g. from the DAT Freight Rate index
    fuel_surcharge_pct: float = 0.0   # e.g. tied to regional_demand.macro_signals.national_diesel_reference
    permit_cost: float = 0.0
    escort_vehicle_cost: float = 0.0
    assembly_disassembly_cost: float = 0.0

    def __post_init__(self):
        if self.distance_miles < 0:
            raise ValueError(f"distance_miles must be non-negative, got {self.distance_miles}")
        if self.rate_per_mile < 0:
            raise ValueError(f"rate_per_mile must be non-negative, got {self.rate_per_mile}")
        if self.fuel_surcharge_pct < 0:
            raise ValueError(f"fuel_surcharge_pct must be non-negative, got {self.fuel_surcharge_pct}")
        for name in ("permit_cost", "escort_vehicle_cost", "assembly_disassembly_cost"):
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value}")


def linehaul_cost(i: TransportCostInputs) -> float:
    return i.distance_miles * i.rate_per_mile * (1 + i.fuel_surcharge_pct / 100.0)


def total_transport_cost(i: TransportCostInputs) -> float:
    """Shape matches logistics_friction.transport.estimated_cost."""
    return (
        linehaul_cost(i)
        + i.permit_cost
        + i.escort_vehicle_cost
        + i.assembly_disassembly_cost
    )


if __name__ == "__main__":
    # Flatbed move of a compact track loader, Dallas TX -> New England, ~1550 mi.
    ctl_move = TransportCostInputs(
        distance_miles=1550,
        rate_per_mile=2.10,
        fuel_surcharge_pct=12.0,
    )
    print("CTL flatbed move:", round(total_transport_cost(ctl_move), 2))

    # Oversize crane move requiring RGN, permits, and two escorts.
    crane_move = TransportCostInputs(
        distance_miles=420,
        rate_per_mile=4.75,
        fuel_surcharge_pct=12.0,
        permit_cost=850,
        escort_vehicle_cost=1200,
        assembly_disassembly_cost=3000,
    )
    print("Crane RGN move:", round(total_transport_cost(crane_move), 2))

    # Negative inputs must be rejected, not silently produce a negative cost.
    for bad_kwargs in [
        {"distance_miles": -100, "rate_per_mile": 2.0},
        {"distance_miles": 100, "rate_per_mile": -2.0},
        {"distance_miles": 100, "rate_per_mile": 2.0, "fuel_surcharge_pct": -50.0},
    ]:
        try:
            TransportCostInputs(**bad_kwargs)
            raise AssertionError(f"expected ValueError for {bad_kwargs}")
        except ValueError as e:
            print("negative input correctly rejected:", bad_kwargs, "->", e)
