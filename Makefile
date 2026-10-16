run:
	uv run scripts/run_all.py

quick:
	uv run scripts/run_all.py --quick

validate:
	uv run scripts/validate_data.py

test:
	uv run pytest -q

lint:
	uv run ruff check src scripts tests

.PHONY: run quick validate test lint
