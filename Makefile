.PHONY: setup dev test lint

setup:
	./scripts/setup.sh

dev:
	./scripts/dev.sh

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/python -m compileall -q app tests
