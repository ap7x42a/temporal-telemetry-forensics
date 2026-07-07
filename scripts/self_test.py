#!/usr/bin/env python3
"""Falsifiable self-test for temporal_scan.

FAILS if the tool cannot separate a dead one-day burst or a died-recently
generator from a live channel -- the exact distinctions this skill exists to make,
and the ones a naive `count` cannot. Includes the naive-baseline contrast: a plain
count ranks the dead burst #1 while the temporal cut demotes it to residue.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import temporal_scan as T  # noqa: E402

NOW = datetime(2026, 7, 5, tzinfo=timezone.utc)


def fixture_rows():
    rows = []
    # live: 3/day for the last 10 days, ending today
    for d in range(10):
        for _ in range(3):
            rows.append((NOW - timedelta(days=d), "live"))
    # dead one-day burst: 1000 rows inside ~50 minutes, 10 days ago (a backfill)
    for i in range(1000):
        rows.append((NOW - timedelta(days=10) + timedelta(minutes=i * 0.05), "dead_burst"))
    # died-recently: ran daily for weeks, then went silent 8 days ago
    for d in range(8, 22):
        rows.append((NOW - timedelta(days=d), "died_recently"))
    return rows


def main():
    res = T.scan(fixture_rows(), now=NOW, stale_days=3, window_days=7, burst_hours=24)
    by = {c["channel"]: c for c in res["channels"]}

    # 1. live channel: not dead, has activity inside the live window
    assert by["live"]["dead"] is False, "live channel wrongly flagged dead"
    assert by["live"]["live_count"] > 0, "live channel has no live-window rows"

    # 2. volume != liveness: the dead burst dominates by count yet is flagged dead residue
    assert by["dead_burst"]["count"] > by["live"]["count"], "fixture invalid: burst should dominate volume"
    assert by["dead_burst"]["dead"] is True, "dead burst not flagged dead (volume masked the death)"
    assert by["dead_burst"]["single_burst"] is True, "dead burst not recognized as a single burst"
    assert by["dead_burst"]["residue"] is True, "dead burst not classified as historical residue"

    # 3. a generator that ran for weeks then stopped is DEAD (scarcity vs death)
    assert by["died_recently"]["dead"] is True, "died-recently generator not flagged dead"
    assert by["died_recently"]["single_burst"] is False, "died-recently wrongly called a burst"

    # 4. NAIVE-BASELINE CONTRAST: a plain count ranks the dead burst #1; the temporal
    #    cut excludes it from the live set. The two MUST disagree -- that is the point.
    naive_top = max(res["channels"], key=lambda c: c["count"])["channel"]
    assert naive_top == "dead_burst", "fixture: naive top should be the dead burst"
    live_generators = [c["channel"] for c in res["channels"] if not c["dead"]]
    assert naive_top not in live_generators, "temporal cut failed to separate residue from live"

    # 5. hostile: empty input must not crash and must report zero channels
    empty = T.scan([], now=NOW)
    assert empty["summary"]["channels"] == 0, "empty input mishandled"

    print("temporal_scan self-test: PASS (dead-burst, died-recently, and live correctly separated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
