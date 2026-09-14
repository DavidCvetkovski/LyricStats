# Drills

Break the system on purpose, on a cluster where it costs nothing, and practise the part that
matters on call: noticing, finding the cause, fixing it, and explaining what happened.

Run each drill yourself before talking about it. Pick one, start a timer, and try to answer
the questions **from the dashboard, alerts and `kubectl` alone** before reading the
"what should happen" notes.

Keep four windows open:

```bash
kubectl --context k3d-lyricstats -n lyricstats get pods -w
```
```bash
kubectl --context k3d-lyricstats -n lyricstats logs -f deploy/alert-sink
```
```bash
kubectl --context k3d-lyricstats -n lyricstats logs -f deploy/loadgen
```

…and the dashboard at http://grafana.localhost:8080/d/lyricstats-overview.

---

## 1. The database disappears

```bash
make drill-db-outage      # later: make drill-db-restore
```

**Questions:** What do users see, and how quickly? Which alert fires first, and how long
after? Why does the API still show 2/2 pods ready? Now delete one API pod
(`kubectl -n lyricstats delete pod <one api pod>`) while the database is still down: what
happens to the replacement, and why? Once the database is back, which pods recover by
themselves and which need a nudge?

<details><summary>What should happen</summary>

- The loadgen summary switches to `500=` within one 30-second window. The prerendered web
  pages keep loading.
- `LyricStatsPostgresDown` fires after about 1–1.5 minutes (scrape interval + `for: 1m`).
- `LyricStatsErrorBudgetFastBurn` needs the *1-hour* error ratio above 14.4%, which takes
  about 9 minutes of total failure, plus `for: 2m`. The symptom alert trails the cause alert
  by roughly 10 minutes. That's the trade-off of burn-rate alerting: few false pages, but a
  slower page for a sudden, total failure.
- API pods stay ready because `/health` doesn't touch the database. That's deliberate.
- A new API pod crash-loops: `lyricstats/db.py` runs `create_all()` at import time, so the
  process can't start without the database. `LyricStatsPodCrashLooping` fires.
- After restore, running pods recover on their own (`pool_pre_ping`). The crash-looping pod
  waits out its back-off (up to 5 minutes) unless you delete it.
</details>

---

## 2. A bad config rollout

```bash
make drill-bad-config     # fix: make drill-rollback
```

**Questions:** Do users notice? What stops this from becoming an outage? How would you find
out *what* changed if you hadn't made the change yourself?

<details><summary>What should happen</summary>

- The new ReplicaSet's pod crashes on start (`password authentication failed`) and never
  becomes ready. Because the rollout uses `maxUnavailable: 0`, the two old pods keep serving:
  error ratio stays at 0, users notice nothing.
- `kubectl rollout status` hangs; `LyricStatsPodCrashLooping` fires for the new pod.
- `kubectl -n lyricstats rollout history deploy/lyricstats-api` and
  `kubectl -n lyricstats get rs` show the new revision; `kubectl describe` of the new pod
  shows the changed environment variable.
</details>

---

## 3. Memory limit too small

```bash
make drill-oom            # fix: make drill-rollback
```

**Questions:** How do you tell an out-of-memory kill from an application crash, without
reading the logs?

<details><summary>What should happen</summary>

- The new pod is killed while importing its dependencies. `kubectl describe pod` shows
  `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`. Logs are usually empty,
  which is itself a clue.
- As in drill 2, the old pods keep serving.
</details>

---

## Afterwards

Write it up as if it had been real, using [`../incidents/TEMPLATE.md`](../incidents/TEMPLATE.md):
a timeline from the alert log, what users saw, what went well, what was slow, and what you
would change. [`../incidents`](../incidents) has a worked example.
