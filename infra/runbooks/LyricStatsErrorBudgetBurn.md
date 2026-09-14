# LyricStatsErrorBudgetFastBurn / LyricStatsErrorBudgetSlowBurn

## Meaning

Too many API requests are returning 5xx for the SLO (99% of requests succeed over 30 days).

- **Fast burn (critical):** more than 14.4% of requests failed over both the last 5 minutes
  and the last hour. The whole month's budget goes in about two days at this rate.
- **Slow burn (warning):** more than 6% failed over both the last 30 minutes and the last
  6 hours. The budget goes in about five days.

This is a *symptom* alert: users are being hurt, cause unknown. It usually fires alongside a
cause alert (Postgres down, crash loops). If one of those is firing, go to its runbook first.

## Impact

Artist pages and search show errors for the share of requests in the alert description.
404s (unknown artists) are not counted; they are correct answers.

## Diagnose

1. **Is a cause alert already firing?** Check http://prometheus.localhost:8080/alerts.
   `LyricStatsPostgresDown` or `LyricStatsPodCrashLooping` explain most 5xx.
2. **Which routes fail?** In Prometheus:
   ```promql
   sum by (route, status) (rate(lyricstats_http_requests_total{job="lyricstats-api",status=~"5.."}[5m]))
   ```
   One route failing points to that code path; every route failing points to a shared
   dependency (the database).
3. **All pods, or one?**
   ```promql
   sum by (pod) (rate(lyricstats_http_requests_total{job="lyricstats-api",status=~"5.."}[5m]))
   ```
   One bad pod: see step 5. All pods: the problem is shared.
4. **Read the errors.** Tracebacks name the failing call:
   ```bash
   kubectl -n lyricstats logs deploy/lyricstats-api --since=10m | grep -B2 -A20 Traceback | head -80
   ```
5. **Did something just change?**
   ```bash
   kubectl -n lyricstats rollout history deploy/lyricstats-api
   kubectl -n lyricstats get events --sort-by=.lastTimestamp | tail -20
   ```

## Mitigate

- **Started with a rollout:** roll back first, investigate after.
  ```bash
  kubectl -n lyricstats rollout undo deploy/lyricstats-api
  kubectl -n lyricstats rollout status deploy/lyricstats-api
  ```
- **One pod is bad:** delete it; the Deployment replaces it.
  ```bash
  kubectl -n lyricstats delete pod <pod>
  ```
- **The database is the cause:** follow [LyricStatsPostgresDown](LyricStatsPostgresDown.md).

The fast-burn alert clears about 5 minutes after errors stop (the 5-minute window drops
below the threshold).

## Follow up

- Note how much budget the incident used: `lyricstats:sli_error_ratio:rate1h` over the
  incident window, times its duration.
- Write it up if the fast burn paged: see [`../incidents`](../incidents).
