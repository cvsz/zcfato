VENV_PYTHON := $(wildcard $(CURDIR)/venv/bin/python $(CURDIR)/venv/Scripts/python.exe)
PYTHON ?= $(if $(VENV_PYTHON),$(firstword $(VENV_PYTHON)),python3)
RUFF := $(PYTHON) -m ruff
PYTEST := $(PYTHON) -m pytest

.PHONY: help venv setup validate validate-template format lint test build security clean ci

help:
	@printf '%s\n' 'Project tasks:' '  venv              Create virtual environment if it does not exist' '  setup             Install the root and control-server development dependencies' '  validate-template Run repository structure and Markdown link validation' '  format            Check control-server formatting' '  lint              Lint the control-server source and tests' '  test              Run root and control-server test suites' '  build             Package desktop apps on Windows' '  security          Audit root and installed Python dependencies' '  clean             Remove cache directories' '  ci                Run repository, format, lint, test, and security checks'

venv:
	@test -d $(CURDIR)/venv || python3 -m venv $(CURDIR)/venv

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pip install -e 'control-server[lint,test]'

validate-template:
	python3 scripts/validate_repo.py
	python3 -m unittest discover -s tests -p 'test_bootstrap.py' -v

validate: validate-template

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

clean:
	find . \( -name .git -o -name .pytest_cache -o -name .ruff_cache -o -name .venv -o -name venv -o -name node_modules -o -name build -o -name dist \) -prune -o -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . \( -name .git -o -name .ruff_cache -o -name .venv -o -name venv -o -name node_modules -o -name build -o -name dist -o -name __pycache__ \) -prune -o -type d -name '.pytest_cache' -prune -exec rm -rf {} +
	find . \( -name .git -o -name .pytest_cache -o -name .venv -o -name venv -o -name node_modules -o -name build -o -name dist -o -name __pycache__ \) -prune -o -type d -name '.ruff_cache' -prune -exec rm -rf {} +

ci: validate-template format lint test security
