.PHONY: install run api test fmt lint clean

install:
	uv sync --extra dev

# Starts FastAPI (:8000) + Next.js (:3000) together.
run:
	./start.sh

# Backend only.
api:
	uv run uvicorn backend.main:app --reload --port 8000

test:
	uv run pytest -q

fmt:
	uv run ruff format .

lint:
	uv run ruff check .

clean:
	rm -rf .venv .pytest_cache .ruff_cache __pycache__ */__pycache__
