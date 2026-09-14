# LyricStatsPostgresDown

## Meaning

`postgres-exporter` has been unable to connect to Postgres for 1 minute (`pg_up == 0`), or
the exporter itself has stopped reporting.

## Impact

Every API endpoint reads the database, so API requests return 500. The API pods stay
"ready", because `/health` deliberately does not check the database, so traffic keeps
reaching them and failing fast rather than hanging.

**Known sharp edge:** `lyricstats/db.py` creates tables when the module is imported. An API
pod that *starts* while Postgres is down crashes on import and goes into CrashLoopBackOff.
While this alert is firing, do **not** restart or roll API pods, and don't drain the node.
Pods that are already running recover by themselves once the database is back.

## Diagnose

1. **Is the database pod there?**
   ```bash
   kubectl -n lyricstats get statefulset,pod,pvc -l app.kubernetes.io/name=postgres
   ```
   - `0/0` replicas: someone scaled it down. `kubectl -n lyricstats get events --sort-by=.lastTimestamp | tail`
   - `Pending`: usually the PersistentVolumeClaim. `kubectl -n lyricstats describe pod postgres-0`
   - `CrashLoopBackOff`: read its logs (step 2).
   - `Running` but not ready: Postgres is starting, recovering, or refusing connections.
2. **Postgres's own logs:**
   ```bash
   kubectl -n lyricstats logs postgres-0 --tail=50
   kubectl -n lyricstats logs postgres-0 --previous --tail=50   # if it restarted
   ```
   Look for `could not write`, `No space left on device`, `database system is shut down`,
   and `FATAL: password authentication failed`.
3. **Can the API reach it?**
   ```bash
   kubectl -n lyricstats exec deploy/lyricstats-api -- python -c \
     "import os, psycopg; psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=3).execute('select 1'); print('ok')"
   ```
4. **Is only the exporter broken?** If Postgres is healthy and the API is serving 200s,
   check `kubectl -n lyricstats logs deploy/postgres-exporter`.

## Mitigate

- Scaled down: `kubectl -n lyricstats scale statefulset/postgres --replicas=1`, then
  `kubectl -n lyricstats rollout status statefulset/postgres`.
- Crashing on a full volume: expand the PVC or clear space; data is on `data-postgres-0`.
- Wrong password (the Secret changed): put the old password back, or change it in Postgres
  to match the Secret, then restart the exporter and API.

After recovery, confirm the API is serving again (the error ratio drops to 0 within a few
scrapes) and that no API pod is stuck in CrashLoopBackOff from the sharp edge above:

```bash
kubectl -n lyricstats get pods -l app.kubernetes.io/name=lyricstats-api
```

A pod still in back-off can take up to 5 minutes to try again; `kubectl delete pod` skips the wait.

## Follow up

- Move table creation out of import time (a migration Job or an explicit startup step with
  retries) so API pods can start while the database is unavailable.
