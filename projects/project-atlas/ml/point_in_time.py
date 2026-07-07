"""Point-in-time-correct (AS-OF) join utilities.

Prevents temporal data leakage when building training feature vectors: a
feature value is only valid to join if it was observable at or before the
cutoff (typically sold_transaction.sale.sold_at, or
training_labels.prediction_snapshot.predicted_at). Every time-varying
schema in this project carries an AS-OF timestamp field for this purpose:
logistics_friction.computed_at, regional_demand.computed_at,
listing.asset.telematics.reported_at, sold_transaction.source.captured_at
/ sale.sold_at, listing.source.scraped_at (see schemas/README.md).

Pure stdlib (bisect only) -- no pandas/numpy in this environment. Two
entry points:
  - PointInTimeIndex.as_of(): single lookup, O(log n) via bisect.
  - sort_merge_as_of_join(): one forward pass over sorted rows for
    building a full training table ("early-stop sort-merge join"),
    O(n+m) instead of one bisect per row.
"""

import bisect
from collections import defaultdict


class PointInTimeIndex:
    """Indexes (entity_key, timestamp, value) rows for AS-OF lookups.

    timestamp must sort correctly with plain comparison (e.g. canonical
    ISO 8601 strings or datetime objects), consistent within one index.
    """

    def __init__(self, rows):
        by_entity = defaultdict(list)
        for entity_key, timestamp, value in rows:
            by_entity[entity_key].append((timestamp, value))
        self._timestamps = {}
        self._values = {}
        for entity_key, pairs in by_entity.items():
            pairs.sort(key=lambda p: p[0])
            self._timestamps[entity_key] = [p[0] for p in pairs]
            self._values[entity_key] = [p[1] for p in pairs]

    def as_of(self, entity_key, cutoff):
        """Latest value with timestamp <= cutoff, or None if nothing was observable yet.

        Never returns a value timestamped after cutoff -- that's the whole
        point. No fallback to "closest" or "any" row.
        """
        timestamps = self._timestamps.get(entity_key)
        if not timestamps:
            return None
        idx = bisect.bisect_right(timestamps, cutoff) - 1
        if idx < 0:
            return None
        return self._values[entity_key][idx]


def sort_merge_as_of_join(left_rows, index: PointInTimeIndex):
    """left_rows: iterable of (entity_key, cutoff), ideally grouped/sorted by
    entity_key then cutoff ascending, matching how the index is sorted.

    Yields (entity_key, cutoff, value_or_None). Advances a per-entity
    pointer forward only -- never re-scans earlier timestamps -- giving
    O(n+m) total work across a full left table instead of repeated
    per-row bisects.
    """
    pointers = defaultdict(int)
    for entity_key, cutoff in left_rows:
        timestamps = index._timestamps.get(entity_key, [])
        values = index._values.get(entity_key, [])
        p = pointers[entity_key]
        while p < len(timestamps) and timestamps[p] <= cutoff:
            p += 1
        pointers[entity_key] = p
        value = values[p - 1] if p > 0 else None
        yield entity_key, cutoff, value


if __name__ == "__main__":
    # regional_demand-style rows: (category|region, computed_at, avg_sold_price).
    # Deliberately out of chronological order, and includes a row that was
    # *backfilled* on 2024-08-15 describing data alongside a later 2024-09-01
    # snapshot -- the index must sort by computed_at, not insertion order.
    rows = [
        ("skid_steer|US-TX", "2024-06-01", 38000),
        ("skid_steer|US-TX", "2024-07-01", 39500),
        ("skid_steer|US-TX", "2024-09-01", 41000),
        ("skid_steer|US-TX", "2024-08-15", 40200),
    ]
    index = PointInTimeIndex(rows)

    # A sale on Aug 15, 2024 must NOT see the Sept 1 snapshot.
    cutoff = "2024-08-15"
    value = index.as_of("skid_steer|US-TX", cutoff)
    print(f"as_of({cutoff}):", value)
    assert value == 40200, "leaked a future snapshot"

    # Before any data existed for this entity.
    assert index.as_of("skid_steer|US-TX", "2024-01-01") is None
    assert index.as_of("unknown_entity", "2024-08-15") is None

    # sort_merge_as_of_join over a small left table.
    left = [
        ("skid_steer|US-TX", "2024-06-15"),
        ("skid_steer|US-TX", "2024-08-15"),
        ("skid_steer|US-TX", "2024-12-01"),
    ]
    results = list(sort_merge_as_of_join(left, index))
    for entity_key, join_cutoff, joined_value in results:
        print(entity_key, join_cutoff, "->", joined_value)
    assert results == [
        ("skid_steer|US-TX", "2024-06-15", 38000),
        ("skid_steer|US-TX", "2024-08-15", 40200),
        ("skid_steer|US-TX", "2024-12-01", 41000),
    ], "sort_merge_as_of_join produced an unexpected (possibly leaked) result"

    print("All self-tests passed: no future snapshot was ever selected.")
