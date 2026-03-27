.PHONY: demo test-demo test-onyx-target serve-dashboard test bootstrap-submodules update-submodules

demo:
	bash scripts/run-demo.sh

test-demo:
	bash scripts/test-demo.sh

test-onyx-target:
	bash scripts/test-onyx-target.sh

serve-dashboard:
	bash scripts/start-control-plane.sh

test:
	pytest -q

bootstrap-submodules:
	bash scripts/bootstrap-submodules.sh

update-submodules:
	bash scripts/update-submodules.sh
