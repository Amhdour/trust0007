.PHONY: demo test-demo test-onyx-target test-governance serve-dashboard serve-onyx test bootstrap-submodules update-submodules validate-upstream list-upstream-default list-upstream-opt-in sync-upstream-pins stage-default-upstream init-client-template bootstrap-live smoke-live test-live-stack health-check up-dev up-live down-dev down-live verify-live

CLIENT_NAME ?= Example Client
CLIENT_SLUG ?= example-client
ENGAGEMENT_TRACK ?= secure-starter-kit
PRIMARY_RUNTIME ?= Onyx

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
	python scripts/smoke-live-onyx-handoff.py

test-live-stack:
	pytest -q tests/integration/test_strict_live_onyx_end_to_end.py tests/integration/test_strict_live_dify_end_to_end.py

health-check:
	bash scripts/check-project-health.sh

up-dev:
	docker compose --env-file compose/.env -f compose/docker-compose.yml up -d

down-dev:
	docker compose --env-file compose/.env -f compose/docker-compose.yml down

verify-live:
	bash scripts/verify-live-env.sh .env.live

up-live: verify-live
	docker compose --env-file .env.live -f compose/docker-compose.production.yml -f compose/docker-compose.live.yml up -d

down-live:
	docker compose --env-file .env.live -f compose/docker-compose.production.yml -f compose/docker-compose.live.yml down
