---
name: temporal-telemetry-forensics
description: Use before drawing any conclusion from an accumulating operational store — a DB table, telemetry/event stream, JSONL ledger, or metric that grows over time. Anchor the analysis to the events that changed the data-generating process; a plain aggregate over a non-stationary store will invert your causality.
metadata:
  self_test: "python3 scripts/self_test.py"
---

# Temporal Telemetry Forensics

**an accumulating store is not one population — it is every regime stacked on top of the last**

## The one rule

A store that grows over time is a **non-stationary process**. Its rows were produced by code that changed underneath them — resets, fix commits, schema migrations, channels switching on and off. A single aggregate (`GROUP BY outcome`, a lifetime total, one mean) silently averages across every regime and reports a number that describes **no moment that ever existed**. Anchor to the change-boundaries and bucket by time *before* you aggregate, or the totals will lie to you with a straight face.

> The lifetime total is the sum of every regime you forgot to separate.

## The failure that authored this

An operational audit treated a lifetime aggregate as live behavior. The total
was technically true, but bucketing by day showed almost all rows came from a
single short backfill. The aggregate hid the actual incident: the real signal had
gone to zero days earlier and stayed there. The first diagnosis chased dead
residue while the live generator's death sat unlit in the totals.

## The procedure

1. **Timeline before totals.** Before any `count(*)`, establish the change-boundary timeline: `git log` the relevant fixes, resets, and migrations; find the data floor (the last clean-slate/reset epoch — rows before it are a different universe). Convert every boundary and every timestamp to **one timezone** first; mixed `-05:00`/`Z` stamps invert causality by hours.
2. **Bucket, don't lump.** Cut the data `GROUP BY date_trunc('day'|'week', ts)`, per channel, against that timeline. A bare `GROUP BY <category>` with no time axis is the smell.
3. **Lifetime total ≠ live rate.** State both and decide on the **live rate** (last-N-days per channel). A huge total can be dead residue; the tiny recent rate is the real operating point.
4. **Last-write is a liveness probe.** For every channel/provenance, compute `max(ts)`. A channel whose newest row is stale is a **dead generator** no matter how large its lifetime count — and a dead generator is usually the actual bug. Aggregate volume *masks* dead generators; per-channel freshness reveals them.
5. **Cross each boundary, re-ask.** For every change-boundary, ask "what did this do to each channel's rate?" A rate that drops to zero at a commit's date is that commit's fingerprint.

## Naive baseline that fails

`SELECT category, count(*) FROM store GROUP BY category ORDER BY 2 DESC`. It cannot distinguish a one-day dead spike from a live channel, cannot see a generator that died, and cannot attribute a change to a boundary. The temporal cut — per-day counts with per-channel `first_seen`/`last_seen` — is the instrument that can return "no."

## Red flags — stop and add the time axis

| Rationalization | Reality |
|---|---|
| "The total says 1,141, so that channel is big." | A total is every regime summed. Bucket by day; the 1,141 may be one dead afternoon. |
| "There are ~0 genuine rows, so the signal never existed." | The generator may have *died*. Check `max(ts)` per channel before concluding scarcity. |
| "I'll GROUP BY category and read off the answer." | No time axis = no causality. Category totals over a non-stationary store describe no real moment. |
| "The store looks healthy — 2,000+ rows." | Volume hides death. A store can be 90% stale residue with its live rate at zero. |
| "The timestamps are close enough." | A 5-hour zone error inverts before/after. Normalize to one zone first. |

## Done means

- The change-boundary timeline (resets, fixes, migrations) is written down and every timestamp is in one zone.
- Every load-bearing claim is stated as a **rate over a named window**, not a lifetime total — or the two are explicitly distinguished.
- Each channel's `last_seen` was checked; dead generators are named as dead.
- Any conclusion that changed between the aggregate and the temporal cut is flagged — that delta is the whole point of the skill.

## Harness

The temporal cut is deterministic — a real tool, not prose to re-derive:

- `scripts/temporal_scan.py` — reads CSV `(timestamp, channel)` rows (pipe a `psql … COPY … TO STDOUT CSV HEADER` straight in) and emits, per channel: `count`, `first_seen`/`last_seen`, `live_rate_per_day` over a window, and the `dead` / `single_burst` / `residue` flags. `residue = dead AND single_burst` is the one-afternoon-backfill-that-looks-huge case; a channel whose `last_seen` is stale is a dead generator no matter its `count`. Measurement-only.
- `scripts/self_test.py` (declared in `metadata.self_test`) is the falsifiable receipt: it builds a live channel, a 1000-row/50-minute dead burst, and a died-8-days-ago generator, and asserts the tool flags them correctly **and** that the naive `count` ranking disagrees with the temporal cut — the naive-baseline contrast. If that distinction ever breaks, the self-test fails.

Run it: `python3 scripts/self_test.py`.

## Scope

This governs how to *read* an accumulating store before drawing a conclusion.
It is not a time-varying confidence model; it is the precondition that prevents a
non-stationary aggregate from lying before any estimator or dashboard sees it.
Higher-priority safety and operator instructions win.
