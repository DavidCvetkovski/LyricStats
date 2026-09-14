# YYYY-MM-DD: <what users experienced, in a few words>

| | |
|---|---|
| **Status** | Resolved |
| **Severity** | SEV-1 (total outage) / SEV-2 (major feature broken) / SEV-3 (degraded) |
| **Duration** | from first user impact to full recovery |
| **Detected by** | which alert, or who noticed |
| **Error budget used** | failed requests during the incident, as a share of the 30-day budget |

## Summary

Three or four sentences a non-engineer could follow: what broke, who noticed, how it was
fixed, and whether it can happen again.

## Impact

What users saw, for how long, and how many requests failed. Numbers come from Prometheus
and the loadgen log, not from memory.

## Timeline (UTC)

| Time | Event |
|---|---|
| hh:mm:ss | Trigger |
| hh:mm:ss | First user-visible errors |
| hh:mm:ss | First alert fires |
| hh:mm:ss | Cause identified |
| hh:mm:ss | Mitigation applied |
| hh:mm:ss | Users recovered |
| hh:mm:ss | All alerts resolved |

## Root cause

The chain of events, including *why* each safeguard didn't stop it. Blameless: describe
what the system allowed, not who did it.

## What went well

## What went badly, or was slow

## Action items

| Action | Type | Priority |
|---|---|---|
| | prevent / detect / mitigate | P1 / P2 / P3 |
