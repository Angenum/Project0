.PHONY: install test lint format run docker-up docker-down

install:
	pip install -e ".[dev,postgres]"

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src tests
	mypy src

format:
	black src tests
	ruff check --fix src tests

run:
	python -m src.run

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down -v
