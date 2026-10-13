SHELL := /bin/sh

.PHONY: help validate-template setup format lint test build security ci

help:
	@printf '%s\n' 'Template: validate-template' 'Project (configure before use): setup format lint test build security ci' 'Bootstrap: python3 scripts/bootstrap.py --help'

validate-template:
	python3 scripts/validate_repo.py
	python3 -m unittest discover -s tests -v

setup:
	@echo 'Setting up project dependencies...'
	@if [ -f requirements.txt ]; then \
		echo 'Checking Python dependencies...'; \
		if command -v pip > /dev/null 2>&1; then \
			pip list --quiet | grep -q "requirements.txt" || echo "Python dependencies would be installed from requirements.txt"; \
		fi; \
	fi
	@echo 'Installing dev dependencies...'
	@if [ -f requirements-dev.txt ]; then \
		if command -v pip > /dev/null 2>&1; then \
			pip list --quiet | grep -q "requirements-dev.txt" || echo "Dev dependencies would be installed from requirements-dev.txt"; \
		fi; \
	fi
	@echo 'Installing git hooks...'
	@if [ -f .githooks/install.sh ]; then \
		chmod +x .githooks/install.sh && .githooks/install.sh || echo 'Warning: Git hooks installation had issues'; \
	fi
	@echo 'Project setup complete'

format:
	@echo 'Checking code formatting...'
	@if command -v black > /dev/null; then \
		black --check . --exclude \".venv|.git\" > /dev/null 2>&1 || black . --exclude \".venv|.git\" --quiet; \
	fi
	@if command -v prettier > /dev/null; then \
		prettier --check . --exclude \".git\" > /dev/null 2>&1 || prettier . --exclude \".git\" --write; \
	fi
	@echo 'Formatting check complete'
	@echo 'Checking code formatting...'
	@if command -v black > /dev/null; then \
		black --check . --exclude ".venv|.git" > /dev/null 2>&1 || black . --exclude ".venv|.git" --quiet; \
	fi
	@if command -v prettier > /dev/null; then \
		prettier --check . --exclude ".git" > /dev/null 2>&1 || prettier . --exclude ".git" --write; \
	fi
	@echo 'Formatting check complete'

lint:
	@echo 'Running lint checks...'
	@if command -v flake8 > /dev/null; then \
		flake8 . --exclude ".venv|.git" || true; \
	fi
	@if command -v shellcheck > /dev/null; then \
		shellcheck $(shell find . -name "*.sh" -not -path "./.git/*" -not -path "./.*" -not -path "./.venv/*"); \
	fi
	@echo 'Linting complete'

test:
	@echo 'Running tests...'
	@if command -v pytest > /dev/null; then \
		pytest -q; \
	else \
		python3 -m unittest discover -s tests -v; \
	fi
	@echo 'Testing complete'

build:
	@echo 'Building project artifacts...'
	@if [ -f build.py ]; then \
		python3 build.py; \
	elif [ -f setup.py ]; then \
		python3 setup.py build; \
	else \
		echo 'No build configuration found'; \
	fi
	@echo 'Build complete'

security:
	@echo 'Running security checks...'
	@if command -v safety > /dev/null; then \
		safety check --json > /dev/null || safety check; \
	fi
	@if [ -f .github/workflows/codeql.yml ]; then \
		echo 'CodeQL workflow configured - run manually for detailed security analysis'; \
	fi
	@echo 'Security checks complete'

ci: validate-template lint test build security
