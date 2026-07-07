#!/usr/bin/env python3
"""temporal_scan.py -- the temporal cut for an accumulating store.

Given rows of (timestamp, channel), decompose by channel into
first_seen / last_seen / count / live-rate, and flag DEAD generators and
single-burst residue -- the distinctions a plain `GROUP BY channel` cannot make.

This is a MEASUREMENT instrument. It reads; it mutates nothing.

Usage:
    psql ... -c "COPY (SELECT ts, channel FROM store) TO STDOUT CSV HEADER" \\
      | python3 scripts/temporal_scan.py --stale-days 3 --window-days 7

Reads CSV (with header) from --input or stdin. Emits JSON to stdout. Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone


def parse_ts(raw):
    """Parse an ISO-8601-ish timestamp to an aware UTC datetime, or None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                dt = None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def scan(rows, *, now=None, stale_days=3.0, window_days=7.0, burst_hours=24.0):
    """rows: iterable of (timestamp: datetime|None, channel). Returns analysis dict.

    A channel is DEAD when its newest row is older than `stale_days` -- a dead
    generator regardless of lifetime volume. A channel is a SINGLE_BURST when all
    its rows fall inside `burst_hours`. `residue` = dead AND single_burst: a
    historical one-shot, not a live channel -- the exact thing a lifetime total
    hides.
    """
    by = defaultdict(list)
    parsed = 0
    for ts, ch in rows:
        if ts is None:
            continue
        by[str(ch)].append(ts)
        parsed += 1

    if now is None:
        all_ts = [t for series in by.values() for t in series]
        # Data-derived reference point: deterministic when data is present.
        now = max(all_ts) if all_ts else datetime.now(timezone.utc)

    stale_before = now - timedelta(days=stale_days)
    window_start = now - timedelta(days=window_days)
    burst = timedelta(hours=burst_hours)

    channels = []
    for ch, series in by.items():
        series.sort()
        first, last = series[0], series[-1]
        span = last - first
        live_count = sum(1 for t in series if t >= window_start)
        dead = last < stale_before
        single_burst = span <= burst
        channels.append({
            "channel": ch,
            "count": len(series),
            "first_seen": first.isoformat(),
            "last_seen": last.isoformat(),
            "span_hours": round(span.total_seconds() / 3600.0, 2),
            "live_count": live_count,
            "live_rate_per_day": round(live_count / max(window_days, 1.0), 3),
            "dead": dead,
            "single_burst": single_burst,
            "residue": dead and single_burst,
        })
    channels.sort(key=lambda c: c["count"], reverse=True)

    summary = {
        "reference_now": now.isoformat(),
        "parsed_rows": parsed,
        "channels": len(channels),
        "live_channels": sum(1 for c in channels if not c["dead"]),
        "dead_channels": sum(1 for c in channels if c["dead"]),
        "single_burst_channels": sum(1 for c in channels if c["single_burst"]),
        "residue_channels": sum(1 for c in channels if c["residue"]),
        "stale_days": stale_days,
        "window_days": window_days,
        "burst_hours": burst_hours,
    }
    return {"summary": summary, "channels": channels}


def _pick(fieldnames, preferred, aliases):
    if preferred in fieldnames:
        return preferred
    for a in aliases:
        if a in fieldnames:
            return a
    return None


def _read_csv(fh, ts_col, channel_col):
    reader = csv.DictReader(fh)
    if reader.fieldnames is None:
        return []
    tcol = _pick(reader.fieldnames, ts_col, ["ts", "timestamp", "time", "at", "created_at"])
    ccol = _pick(reader.fieldnames, channel_col, ["channel", "source", "kind", "type", "outcome", "row_kind"])
    if tcol is None or ccol is None:
        raise SystemExit(f"error: could not resolve timestamp/channel columns; header is {reader.fieldnames}")
    return [(parse_ts(row.get(tcol)), row.get(ccol)) for row in reader]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Temporal cut of an accumulating store (dead-generator + burst detection).")
    ap.add_argument("--input", "-i", help="CSV file with header (default: stdin)")
    ap.add_argument("--ts-col", default="ts", help="timestamp column name (aliases auto-detected)")
    ap.add_argument("--channel-col", default="channel", help="channel/provenance column name (aliases auto-detected)")
    ap.add_argument("--now", help="reference 'now' ISO-8601 (default: max timestamp in the data)")
    ap.add_argument("--stale-days", type=float, default=3.0, help="a channel with no row newer than this is DEAD")
    ap.add_argument("--window-days", type=float, default=7.0, help="live-rate window")
    ap.add_argument("--burst-hours", type=float, default=24.0, help="all rows inside this span => single_burst")
    args = ap.parse_args(argv)

    fh = open(args.input, newline="") if args.input else sys.stdin
    try:
        rows = _read_csv(fh, args.ts_col, args.channel_col)
    finally:
        if args.input:
            fh.close()

    now = parse_ts(args.now) if args.now else None
    result = scan(rows, now=now, stale_days=args.stale_days,
                  window_days=args.window_days, burst_hours=args.burst_hours)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
