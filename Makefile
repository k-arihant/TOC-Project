.PHONY: help install test lint format clean generate-data train run-api run-dashboard docker-up

help:
	@echo "Available commands:"
	@echo "  make install         Install dependencies"
	@echo "  make test            Run pytest test suite"
	@echo "  make lint            Run ruff linter"
	@echo "  make format          Run ruff code formatter"
	@echo "  make generate-data   Generate sample synthetic dataset"
	@echo "  make train           Train baseline anomaly detection models"
	@echo "  make run-api         Start FastAPI server"
	@echo "  make run-dashboard   Start Streamlit dashboard"
	@echo "  make docker-up       Build and run Docker Compose stack"
	@echo "  make clean           Remove cache and temporary files"

install:
	pip install -r requirements.txt -r requirements-dev.txt -r requirements-dashboard.txt

test:
	pytest -q

lint:
	ruff check .

format:
	ruff format .

generate-data:
	python scripts/generate_dataset.py --seed 0 --out data/sample

train:
	python scripts/train_models.py --dataset data/sample --seed 0

run-api:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

run-dashboard:
	streamlit run src/dashboard/app.py --server.port 8501

docker-up:
	docker compose up --build

clean:
	python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')]"
