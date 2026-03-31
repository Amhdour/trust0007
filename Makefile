.PHONY: demo test-demo test-onyx-target test-governance serve-dashboard serve-onyx test bootstrap-submodules update-submodules validate-upstream list-upstream-default list-upstream-opt-in

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
