.PHONY: help reviewer-fast-path demo test-demo test-onyx-target test-governance serve-dashboard serve-onyx test verify validate-policy-schema bootstrap-submodules update-submodules validate-upstream list-upstream-default list-upstream-opt-in sync-upstream-pins stage-default-upstream init-client-template bootstrap-live smoke-live test-live-stack health-check proof-pack preflight-onyx-trust up-dev up-live down-dev down-live verify-live verify-remote-onyx

CLIENT_NAME ?= Example Client
CLIENT_SLUG ?= example-client
ENGAGEMENT_TRACK ?= secure-starter-kit
PRIMARY_RUNTIME ?= Onyx
LIVE_COMPOSE_PROJECT_NAME ?= trust0007_live
LIVE_ENV_FILES ?= compose/.env.production .env.live

help:
	@echo "AI Trust & Security Readiness Control Plane"
	@echo ""
	@echo "Common targets:"
	@echo "  make up-dev             # Start local compose stack"
	@echo "  make down-dev           # Stop local compose stack"
	@echo "  make test               # Run validation + pytest suite"
	@echo "  make verify             # Alias for full local verification"
	@echo "  make test-live-stack    # Run strict live integration tests"
	@echo "  make verify-live        # Validate live env + remote Onyx"
	@echo "  make preflight-onyx-trust # Production preflight checks"
	@echo "  make proof-pack         # Build reviewer-ready proof bundle"
	@echo "  make health-check       # Project health checks"
	@echo ""
	@echo "Career-offer flows:"
	@echo "  Layer Retrofit:         make verify-live"
	@echo "  Secure Starter Kit:     make up-dev && make test"
	@echo "  Launch Gate:            make preflight-onyx-trust"

reviewer-fast-path:
	@echo "1) make test"
	@echo "2) make up-dev"
	@echo "3) open http://127.0.0.1:3000"

demo:
	bash scripts/run-demo.sh

test-demo:
	bash scripts/test-demo.sh

test-onyx-target:
	bash scripts/test-onyx-target.sh

test-governance:
	pytest tests/integration/test_governed_flow.py tests/integration/test_governance_denial.py tests/integration/test_live_end_to_end.py -v

serve-dashboard:
	bash scripts/start-control-plane.sh

serve-onyx:
	bash scripts/start-onyx-lite.sh

test:
	python scripts/validate-upstream-state.py
	python scripts/validate-runtime-policy-schema.py
	pytest -q

validate-policy-schema:
	python scripts/validate-runtime-policy-schema.py

verify:
	python scripts/validate-upstream-state.py
	python scripts/validate-runtime-policy-schema.py
	pytest -q

bootstrap-submodules:
	bash scripts/bootstrap-submodules.sh

update-submodules:
	bash scripts/update-submodules.sh

validate-upstream:
	python scripts/validate-upstream-state.py

list-upstream-default:
	python scripts/list-upstream-groups.py --policy default

list-upstream-opt-in:
	python scripts/list-upstream-groups.py --policy opt_in

sync-upstream-pins:
	python scripts/sync-upstream-pins-from-checkout.py

stage-default-upstream:
	python scripts/stage-default-upstream-checkout.py /tmp/beta011-default-upstream

init-client-template:
	python scripts/init-client-template.py --client-name "$(CLIENT_NAME)" --client-slug "$(CLIENT_SLUG)" --engagement-track "$(ENGAGEMENT_TRACK)" --primary-runtime "$(PRIMARY_RUNTIME)"

bootstrap-live:
	bash scripts/bootstrap-live-governed-path.sh

smoke-live:
	ENV_FILE=compose/.env.production python scripts/smoke-live-onyx-handoff.py

test-live-stack:
	LIVE_STACK_ENV_FILE=compose/.env.production LIVE_COMPOSE_PROJECT_NAME=$(LIVE_COMPOSE_PROJECT_NAME) pytest -q tests/integration/test_strict_live_onyx_end_to_end.py tests/integration/test_live_end_to_end.py

health-check:
	bash scripts/check-project-health.sh

proof-pack:
	python scripts/build-proof-pack.py

up-dev:
	docker compose --env-file compose/.env -f compose/docker-compose.yml up -d

down-dev:
	docker compose --env-file compose/.env -f compose/docker-compose.yml down

verify-remote-onyx:
	bash scripts/verify-remote-onyx.sh $(LIVE_ENV_FILES)

verify-live:
	bash scripts/verify-live-env.sh $(LIVE_ENV_FILES)
	bash scripts/verify-remote-onyx.sh $(LIVE_ENV_FILES)

preflight-onyx-trust:
	bash scripts/preflight-onyx-trust.sh $(LIVE_ENV_FILES)

up-live: verify-live
	docker compose $(foreach env,$(LIVE_ENV_FILES),--env-file $(env)) -p $(LIVE_COMPOSE_PROJECT_NAME) -f compose/docker-compose.production.yml -f compose/docker-compose.live.yml up -d

down-live:
	docker compose $(foreach env,$(LIVE_ENV_FILES),--env-file $(env)) -p $(LIVE_COMPOSE_PROJECT_NAME) -f compose/docker-compose.production.yml -f compose/docker-compose.live.yml down
