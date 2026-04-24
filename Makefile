PROJECT_DIR := $(if $(wildcard trust/Makefile),trust,.)

.PHONY: help reviewer-check
help:
	@echo "trust0007 repository wrapper"
	@echo "Resolved project root: $(PROJECT_DIR)"
	@if [ "$(PROJECT_DIR)" = "trust" ]; then \
		$(MAKE) -C trust help; \
	else \
		echo "No nested trust/ project detected. Run project targets from repository root."; \
	fi

reviewer-check:
	@if [ "$(PROJECT_DIR)" = "trust" ]; then \
		$(MAKE) -C trust help; \
		$(MAKE) -C trust test -n; \
	else \
		echo "No nested trust/ project detected for reviewer-check."; \
		exit 2; \
	fi

.PHONY: %
%:
	@if [ "$(PROJECT_DIR)" = "trust" ]; then \
		$(MAKE) -C trust $@; \
	else \
		echo "Target '$@' is not defined in the root wrapper. Use project-specific targets at repository root."; \
		exit 2; \
	fi
