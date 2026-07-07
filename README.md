# Temporal Telemetry Forensics

Temporal Telemetry Forensics is an agent skill for reading accumulating
operational stores without being fooled by lifetime aggregates.

A store that grows over time is usually not one population. It is many writer
regimes stacked together: deployments, migrations, backfills, resets, disabled
channels, fixed bugs, and stale residue. A single lifetime total can describe no
real moment that ever existed.

## Use It When

- You are drawing conclusions from telemetry, JSONL ledgers, metrics, event
  streams, audit tables, or operational databases.
- A plain `GROUP BY category` or lifetime count is driving the diagnosis.
- The writer changed over time through deployments, migrations, resets, or
  cleanup jobs.
- A large historical count might be a dead burst instead of a live channel.
- A channel with many rows might have stopped writing recently.

## What The Package Includes

- `SKILL.md` - the temporal-reading doctrine and red flags.
- `scripts/temporal_scan.py` - CSV scanner that reports per-channel counts,
  first/last seen timestamps, live rates, dead-channel flags, and burst/residue
  flags.
- `scripts/self_test.py` - regression suite that proves naive count ranking can
  disagree with the temporal cut.
- `agents/openai.yaml` - skill metadata for runtimes that display skill cards.
- `SHA256SUMS.txt` - drift manifest.

## Core Procedure

```text
timeline before totals
-> normalize timestamps
-> bucket by time and channel
-> compute last_seen freshness
-> distinguish lifetime count from live rate
-> cross changes in rate against regime boundaries
```

Every load-bearing claim should name its window. "1,000 events ever" and "0
events in the last seven days" are different facts.

## Using The Scanner

Prepare CSV with `timestamp` and `channel` columns:

```csv
timestamp,channel
2026-07-01T10:00:00Z,feedback
2026-07-01T10:05:00Z,feedback
2026-07-05T11:00:00Z,calibration
```

Run:

```bash
python3 scripts/temporal_scan.py events.csv --as-of 2026-07-07T00:00:00Z --live-window-days 7
```

The scanner is measurement-only. It helps expose dead generators, one-burst
residue, and live rates; it does not decide the root cause for you.

## Install As An Agent Skill

```bash
git clone https://github.com/ap7x42a/temporal-telemetry-forensics.git
cp -a temporal-telemetry-forensics ~/.codex/skills/temporal-telemetry-forensics
```

For project-local skill surfaces, copy the directory into the location your
runtime uses, such as `.agents/skills/temporal-telemetry-forensics`.

## Verify The Package

```bash
python3 scripts/self_test.py
sha256sum -c SHA256SUMS.txt
```

## Limits

This skill governs how to read an accumulating store. It does not replace a
domain-specific causal investigation, schema review, or code trace of the writer
that generated the data.
