.PHONY: install run test fmt lint clean

install:
	uv sync --extra dev

run:
	uv run streamlit run streamlit_app.py

test:
	uv run pytest -q

fmt:
	uv run ruff format .

lint:
	uv run ruff check .

clean:
	rm -rf .venv .pytest_cache .ruff_cache __pycache__ */__pycache__
