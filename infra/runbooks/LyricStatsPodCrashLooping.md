# LyricStatsPodCrashLooping

## Meaning

A container in the `lyricstats` namespace restarted at least 3 times in 10 minutes. The
alert names the pod and container.

## Impact

Depends on which container and how many replicas are left. One API pod crash-looping out of
two halves capacity but users rarely notice. A crash-looping Postgres or both API pods is an
outage, and a critical alert will be firing too.

## Diagnose

1. **Why did the last run end?**
   ```bash
   kubectl -n lyricstats describe pod <pod> | sed -n '/Last State/,/Ready/p'
   ```
   - `Reason: OOMKilled`: memory limit too low, or a leak. Compare against the limit in the
     Deployment and the "Memory working set" panel.
   - `Reason: Error`, exit code 1 or 3: the process crashed. Read the logs (step 2).
   - `Reason: Completed` or liveness failures in Events: the process is alive but not
     answering `/health` in time.
2. **Logs from the crashed run:**
   ```bash
   kubectl -n lyricstats logs <pod> -c <container> --previous --tail=80
   ```
   Common API crashes:
   - `OperationalError ... connection refused` or `could not translate host name "postgres"`:
     the database is unreachable at import time. See [LyricStatsPostgresDown](LyricStatsPostgresDown.md).
   - `password authentication failed`: the `DATABASE_URL` or the Secret is wrong.
   - `ModuleNotFoundError`: the image was built without a dependency.
3. **Did this start with a change?**
   ```bash
   kubectl -n lyricstats rollout history deploy/lyricstats-api
   kubectl -n lyricstats get rs -l app.kubernetes.io/name=lyricstats-api
   ```
   A new ReplicaSet whose pods crash while the old ReplicaSet's pods keep running is a bad
   rollout that `maxUnavailable: 0` caught.

## Mitigate

- Bad rollout: `kubectl -n lyricstats rollout undo deploy/lyricstats-api`
- OOMKilled after a change to limits: roll back the change, or raise the limit.
- Dependency down: fix the dependency; don't restart pods in a loop, since each new start
  hits the same wall.

## Follow up

- Check that the change which caused it would have been caught before deploy, and add the
  missing check (a test, a config lint, a staging rollout).
