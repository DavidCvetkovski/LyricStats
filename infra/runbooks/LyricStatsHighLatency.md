# LyricStatsHighLatency

## Meaning

The 95th percentile of API request duration has been above 1 second for 10 minutes.

## Impact

Search-as-you-type feels broken above a few hundred milliseconds, and artist pages load
slowly. Requests still succeed, so the error-budget alerts stay quiet.

## Diagnose

1. **Which route is slow?**
   ```promql
   histogram_quantile(0.95, sum by (le, route) (rate(lyricstats_http_request_duration_seconds_bucket{job="lyricstats-api"}[5m])))
   ```
2. **More traffic, or slower requests?** Compare "Requests / s" with "Requests in flight" on
   the dashboard. In-flight climbing while traffic is flat means requests are waiting on
   something.
3. **Is the API starved?** The "CPU (cores)" panel, and throttling:
   ```promql
   rate(container_cpu_cfs_throttled_periods_total{namespace="lyricstats",container="api"}[5m])
   ```
   The API has no CPU limit on purpose, so throttling here means the node itself is busy.
4. **Is the database slow?** Look for long-running queries:
   ```bash
   kubectl -n lyricstats exec -it postgres-0 -- psql -U lyricstats -d lyricstats -c \
     "select pid, now() - query_start as running_for, state, left(query, 80)
      from pg_stat_activity where datname = 'lyricstats' and state <> 'idle'
      order by running_for desc limit 10;"
   ```
   Suggestion queries use `LIKE '%key%'` on `artistaggregate.name_key`, which a plain
   B-tree index can't serve. It gets slower as the table grows.

## Mitigate

- Traffic spike and the API is CPU-bound: `kubectl -n lyricstats scale deploy/lyricstats-api --replicas=3`
- A runaway query: cancel it with `select pg_cancel_backend(<pid>);`
- Slowness started with a rollout: `kubectl -n lyricstats rollout undo deploy/lyricstats-api`

## Follow up

- A trigram index would serve the suggestion query:
  `CREATE INDEX CONCURRENTLY ON artistaggregate USING gin (name_key gin_trgm_ops);`
