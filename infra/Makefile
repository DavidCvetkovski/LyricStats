# LyricStats on a local k3s cluster, with Prometheus, Grafana and Alertmanager.
#
# Run from this directory (`cd infra && make up`) or from the repository root
# (`make -C infra up`). Every kubectl and helm call pins the k3d context, so
# nothing here can touch another cluster in your kubeconfig.

SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
INFRA := $(ROOT)/infra

CLUSTER := lyricstats
CONTEXT := k3d-$(CLUSTER)
KUBECTL := kubectl --context $(CONTEXT)
HELM := helm --kube-context $(CONTEXT)
NS := lyricstats

KPS_VERSION := 91.4.0
SEED_DB ?= $(ROOT)/data/lyricstats.db
SEED_LIMIT ?= 2000

.DEFAULT_GOAL := help
.PHONY: help up down cluster images secrets deploy monitoring seed restart status urls \
        grafana-password alerts drill-db-outage drill-db-restore drill-bad-config drill-oom \
        drill-rollback test

help: ## Show this list
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: cluster images secrets deploy monitoring seed urls ## From nothing to a monitored cluster with data

down: ## Delete the cluster and everything in it
	k3d cluster delete $(CLUSTER)

cluster: ## Create the k3d cluster (no-op if it already exists)
	@k3d cluster list $(CLUSTER) >/dev/null 2>&1 || k3d cluster create --config $(INFRA)/cluster/k3d.yaml

images: ## Build the API and web images and load them into the cluster
	docker build --provenance=false -f $(INFRA)/docker/api.Dockerfile -t lyricstats-api:dev $(ROOT)
	docker build --provenance=false -f $(INFRA)/docker/web.Dockerfile -t lyricstats-web:dev $(ROOT)
	k3d image import --cluster $(CLUSTER) lyricstats-api:dev lyricstats-web:dev

secrets: ## Create random Postgres and Grafana passwords, kept only in the cluster
	@$(KUBECTL) create namespace $(NS) --dry-run=client -o yaml | $(KUBECTL) apply -f - >/dev/null
	@$(KUBECTL) create namespace monitoring --dry-run=client -o yaml | $(KUBECTL) apply -f - >/dev/null
	@$(KUBECTL) -n $(NS) get secret postgres-credentials >/dev/null 2>&1 || \
	  $(KUBECTL) -n $(NS) create secret generic postgres-credentials \
	    --from-literal=password="$$(openssl rand -hex 24)"
	@$(KUBECTL) -n monitoring get secret grafana-admin >/dev/null 2>&1 || \
	  $(KUBECTL) -n monitoring create secret generic grafana-admin \
	    --from-literal=admin-user=admin --from-literal=admin-password="$$(openssl rand -hex 16)"

deploy: ## Apply the app manifests and wait for everything to be ready
	$(KUBECTL) apply -k $(INFRA)/k8s
	$(KUBECTL) -n $(NS) rollout status statefulset/postgres --timeout=180s
	$(KUBECTL) -n $(NS) rollout status deploy/lyricstats-api --timeout=180s
	$(KUBECTL) -n $(NS) rollout status deploy/lyricstats-web --timeout=180s

monitoring: ## Install kube-prometheus-stack, then the app's monitors, alerts and dashboard
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update >/dev/null
	$(HELM) upgrade --install kps prometheus-community/kube-prometheus-stack \
	  --version $(KPS_VERSION) --namespace monitoring \
	  --values $(INFRA)/monitoring/values.yaml --wait --timeout 10m
	$(KUBECTL) apply -k $(INFRA)/monitoring

seed: ## Load the $(SEED_LIMIT) largest artist catalogues from data/lyricstats.db
	@test -f "$(SEED_DB)" || { echo "No database at $(SEED_DB); set SEED_DB=..."; exit 1; }
	$(KUBECTL) -n $(NS) rollout status deploy/lyricstats-api --timeout=180s
	python3 $(INFRA)/scripts/seed.py --database "$(SEED_DB)" --limit $(SEED_LIMIT) | \
	  $(KUBECTL) -n $(NS) exec -i statefulset/postgres -- \
	    psql -v ON_ERROR_STOP=1 --single-transaction -U lyricstats -d lyricstats \
	      -c 'TRUNCATE artistaggregate RESTART IDENTITY' \
	      -c '\copy artistaggregate (name, name_key, display_name, song_count, has_sections, stats_json, songs_json, source, built_at) FROM STDIN WITH (FORMAT csv)'
	$(KUBECTL) -n $(NS) exec statefulset/postgres -- \
	  psql -U lyricstats -d lyricstats -c 'SELECT count(*) AS artists FROM artistaggregate'

restart: ## Roll the API and web pods onto freshly imported images
	$(KUBECTL) -n $(NS) rollout restart deploy/lyricstats-api deploy/lyricstats-web
	$(KUBECTL) -n $(NS) rollout status deploy/lyricstats-api --timeout=180s
	$(KUBECTL) -n $(NS) rollout status deploy/lyricstats-web --timeout=180s

status: ## Pods, and any alerts currently firing
	@$(KUBECTL) -n $(NS) get pods -o wide
	@echo
	@$(MAKE) --no-print-directory alerts

alerts: ## Alerts firing or pending in Prometheus right now
	@$(KUBECTL) -n monitoring exec statefulset/prometheus-kps-prometheus -c prometheus -- \
	  wget -qO- 'http://localhost:9090/api/v1/alerts' | \
	  jq -r '[.data.alerts[] | select(.labels.namespace == "$(NS)")] | if length == 0 then "no lyricstats alerts" else .[] | "\(.state)\t\(.labels.alertname)\tsince \(.activeAt)" end'

urls: ## Where everything is
	@echo
	@echo "  App           http://lyricstats.localhost:8080"
	@echo "  Grafana       http://grafana.localhost:8080/d/lyricstats-overview   (admin password: make grafana-password)"
	@echo "  Prometheus    http://prometheus.localhost:8080/alerts"
	@echo "  Alertmanager  http://alertmanager.localhost:8080"
	@echo "  Alert log     kubectl --context $(CONTEXT) -n $(NS) logs -f deploy/alert-sink"
	@echo "  User view     kubectl --context $(CONTEXT) -n $(NS) logs -f deploy/loadgen"
	@echo

grafana-password: ## Print the Grafana admin password
	@$(KUBECTL) -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo

test: ## Unit tests for the metrics middleware (isolated env, leaves the project venv alone)
	cd $(INFRA)/app && uv run --no-project --with fastapi --with httpx --with pytest \
	  --with prometheus-client==0.22.1 pytest -q -p no:cacheprovider

# ── Drills: break something on purpose, watch the alerts, fix it. See drills/README.md ──

drill-db-outage: ## Drill: take Postgres away
	$(KUBECTL) -n $(NS) scale statefulset/postgres --replicas=0
	@echo "Postgres is down. Watch: make alerts, the dashboard, and logs of deploy/alert-sink and deploy/loadgen."

drill-db-restore: ## Drill: bring Postgres back
	$(KUBECTL) -n $(NS) scale statefulset/postgres --replicas=1
	$(KUBECTL) -n $(NS) rollout status statefulset/postgres --timeout=180s

drill-bad-config: ## Drill: roll out an API config with the wrong database password
	$(KUBECTL) -n $(NS) set env deploy/lyricstats-api \
	  DATABASE_URL=postgresql://lyricstats:not-the-password@postgres:5432/lyricstats
	@echo "Rolling out a broken config. Watch: kubectl --context $(CONTEXT) -n $(NS) get pods -w"

drill-oom: ## Drill: roll out an API memory limit too small to start
	$(KUBECTL) -n $(NS) set resources deploy/lyricstats-api -c api --limits=memory=48Mi
	@echo "Rolling out a 48Mi limit. Watch: kubectl --context $(CONTEXT) -n $(NS) get pods -w"

drill-rollback: ## Drill: undo the last API rollout (fixes bad-config and oom)
	$(KUBECTL) -n $(NS) rollout undo deploy/lyricstats-api
	$(KUBECTL) -n $(NS) rollout status deploy/lyricstats-api --timeout=180s
