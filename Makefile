PYTHON ?= python3
RUFF := $(PYTHON) -m ruff
PYTEST := $(PYTHON) -m pytest

.PHONY: help setup validate-template format lint test build security ci

help:
	@printf '%s\n' 'Project tasks:' '  setup             Install the root and control-server development dependencies' '  validate-template Run repository structure and Markdown link validation' '  format            Check control-server formatting' '  lint              Lint the control-server source and tests' '  test              Run root and control-server test suites' '  build             Package desktop apps on Windows' '  security          Audit root and installed Python dependencies' '  ci                Run repository, format, lint, test, and security checks'

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pip install -e 'control-server[lint,test]'

validate-template:
	python3 scripts/validate_repo.py
	python3 -m unittest discover -s tests -p 'test_bootstrap.py' -v

format:
	$(RUFF) format --check control-server/src control-server/tests

lint:
	$(RUFF) check control-server/src control-server/tests

test:
ifeq ($(OS),Windows_NT)
	$(PYTEST) -q tests
else
	xvfb-run -a $(PYTEST) -q tests
endif
	cd control-server && $(PYTEST) -q

ifeq ($(OS),Windows_NT)
build:
	full-build.bat
else
build:
	@echo 'The desktop package build requires Windows; use the build-windows CI job.' >&2
	@exit 2
endif

security:
	$(PYTHON) -m pip_audit -r requirements-dev.txt
	$(PYTHON) -m pip_audit --local --skip-editable

ci: validate-template format lint test security
