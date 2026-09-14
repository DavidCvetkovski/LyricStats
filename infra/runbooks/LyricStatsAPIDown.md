# LyricStatsAPIDown

## Meaning

Prometheus has not been able to scrape a single `lyricstats-api` pod for 2 minutes. Either
there are no API pods, or none of them answers on `:8000/metrics`.

The error-budget alerts cannot see this outage: they count requests the API handled, and a
missing API handles none. That blind spot is why this alert exists.

## Impact

Probably total. Every `/api/*` request fails at the Ingress (Traefik returns 502/503), so
search and artist pages are broken. The prerendered web pages still load.

## Diagnose

1. **Are there pods, and what state are they in?**
   ```bash
   kubectl -n lyricstats get deploy,rs,pods -l app.kubernetes.io/name=lyricstats-api -o wide
   ```
   - `0/2` with no pods: the Deployment was scaled down or deleted. Check
     `kubectl -n lyricstats get events --sort-by=.lastTimestamp | tail`.
   - `CrashLoopBackOff`: see [LyricStatsPodCrashLooping](LyricStatsPodCrashLooping.md).
   - `ImagePullBackOff` / `ErrImagePull`: the image tag doesn't exist in the cluster.
     `kubectl -n lyricstats describe pod <pod> | tail -20`.
   - `Pending`: no room to schedule. `kubectl describe pod <pod>` shows why.
   - `Running` but not ready: the process is up but `/health` fails. Check the logs.
2. **Is it the pods or the path?** From inside the cluster:
   ```bash
   kubectl -n lyricstats run curl --rm -it --restart=Never --image=curlimages/curl -- \
     curl -sS -m 3 http://lyricstats-api:8000/health
   ```
   If this works but Prometheus still can't scrape, check the ServiceMonitor and the
   Service's endpoints: `kubectl -n lyricstats get endpointslices -l kubernetes.io/service-name=lyricstats-api`.

## Mitigate

- Bad rollout: `kubectl -n lyricstats rollout undo deploy/lyricstats-api`
- Scaled to zero: `kubectl -n lyricstats scale deploy/lyricstats-api --replicas=2`
- Image missing locally: rebuild and import (`make -C infra images`), then
  `kubectl -n lyricstats rollout restart deploy/lyricstats-api`

## Follow up

- Why didn't the rollout strategy (`maxUnavailable: 0`) keep the old pods serving? If
  someone deleted or scaled the Deployment by hand, that's a process gap, not a config one.
