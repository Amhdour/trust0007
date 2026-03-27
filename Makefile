.PHONY: demo test-demo test-onyx-target serve-dashboard serve-onyx test bootstrap-submodules update-submodules

demo:
	bash scripts/run-demo.sh

test-demo:
	bash scripts/test-demo.sh

test-onyx-target:
	bash scripts/test-onyx-target.sh

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
