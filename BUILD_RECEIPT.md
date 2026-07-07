# BUILD_RECEIPT - temporal-telemetry-forensics

Harness extracted under the create-harness discipline: keep judgment in prose,
but make the temporal cut executable.

## What was mechanized (kept judgment in prose; extracted the deterministic cut)
- `scripts/temporal_scan.py` — the temporal cut: per-channel `first_seen`/`last_seen`/`count`,
  `live_rate_per_day` over a window, and `dead` / `single_burst` / `residue` flags. Reads CSV
  `(timestamp, channel)`; measurement-only, mutates nothing.

## Falsifiable receipt (`metadata.self_test`)
- `scripts/self_test.py` — fixture: a live channel, a 1000-row/~50-min dead burst (10 days old),
  and a died-8-days-ago generator. Asserts the tool flags dead/residue correctly AND that the
  naive `count` ranks the dead burst #1 while the temporal cut demotes it (the naive-baseline
  contrast that is the whole point).

## Measured this session
- `self_test.py`: **PASS** (exit 0).
- Falsifiability proof: `temporal_scan.scan` patched to never set `dead` → `self_test.py`
  **FAILS** ("dead burst not flagged dead"). The receipt can return "no".

## Not measured (honest gaps)
- Not yet run against a production telemetry export for a target system. The
  fixture proves the dead-burst and died-generator distinctions, not every real
  schema or channel taxonomy.
