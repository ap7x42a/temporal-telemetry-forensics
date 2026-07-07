# Temporal Telemetry Forensics

Reusable Agent Skill for reading accumulating operational stores without being
fooled by lifetime aggregates.

Bucket by time, check last-write freshness, separate dead residue from live
rates, and anchor analysis to regime changes before drawing conclusions.

## Verify

```bash
python3 scripts/self_test.py
sha256sum -c SHA256SUMS.txt
```
