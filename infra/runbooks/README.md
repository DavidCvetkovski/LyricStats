# Runbooks

One page per alert in [`../monitoring/rules.yaml`](../monitoring/rules.yaml). Each alert's
`runbook_url` annotation links straight to its page, so whoever is paged lands here.

Every page follows the same shape: **what the alert means**, **how bad it is for users**,
**how to diagnose**, **how to mitigate**, and **what to follow up on** once it's over.

| Alert | Severity | Page |
|---|---|---|
| LyricStatsErrorBudgetFastBurn | critical | [LyricStatsErrorBudgetBurn](LyricStatsErrorBudgetBurn.md) |
| LyricStatsErrorBudgetSlowBurn | warning | [LyricStatsErrorBudgetBurn](LyricStatsErrorBudgetBurn.md) |
| LyricStatsAPIDown | critical | [LyricStatsAPIDown](LyricStatsAPIDown.md) |
| LyricStatsPostgresDown | critical | [LyricStatsPostgresDown](LyricStatsPostgresDown.md) |
| LyricStatsPodCrashLooping | warning | [LyricStatsPodCrashLooping](LyricStatsPodCrashLooping.md) |
| LyricStatsHighLatency | warning | [LyricStatsHighLatency](LyricStatsHighLatency.md) |

Commands assume the local cluster's context:

```bash
kubectl config use-context k3d-lyricstats
```

Useful everywhere:

| Where | What |
|---|---|
| http://grafana.localhost:8080/d/lyricstats-overview | Service overview dashboard |
| http://prometheus.localhost:8080/alerts | Which alerts are pending or firing |
| http://alertmanager.localhost:8080 | Notifications, silences |
| `kubectl -n lyricstats logs -f deploy/alert-sink` | Every notification that was "sent" |
| `kubectl -n lyricstats logs -f deploy/loadgen` | What synthetic users are seeing, every 30 s |
