# ==============================================================================
# Autonomous Multi-Agent Research Engine Makefile
# ==============================================================================

.PHONY: help setup env run ui eval docker-build docker-run docker-up docker-down docker-logs doppler-env clean

# Default target: display available commands
help:
	@echo =================================================================
	@echo   Autonomous Multi-Agent Research Engine - Command Reference
	@echo =================================================================
	@echo   make env           - Initialize .env from .env.example
	@echo   make doppler-env   - Fetch latest secrets from Doppler to .env
	@echo   make docker-up     - Start Web UI at http://localhost:8081 (Docker)
	@echo   make docker-down   - Stop and remove Docker container
	@echo   make docker-logs   - View live container logs
	@echo   make docker-build  - Build Docker container image
	@echo   make docker-run    - Run CLI research engine inside Docker
	@echo   make setup         - Create virtualenv and install dependencies
	@echo   make ui            - Start Web UI locally (http://localhost:8081)
	@echo   make run           - Run the CLI agent locally
	@echo   make eval          - Run LangSmith automated evaluation suite
	@echo   make clean         - Clean cache and temporary files
	@echo =================================================================

env:
	@if not exist .env (copy .env.example .env && echo Created .env file.) else (echo .env already exists.)

doppler-env:
	doppler secrets download --no-file --format env > .env
	@echo Fetched latest secrets from Doppler to .env

setup:
	python -m venv venv
	.\venv\Scripts\pip install --upgrade pip
	.\venv\Scripts\pip install -r requirements.txt

ui:
	python -m uvicorn src.server:app --host 0.0.0.0 --port 8081 --reload

run:
	python main.py

eval:
	python -m src.evaluate

docker-build:
	docker build -t multi-agent-researcher:latest .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-run:
	docker run -it --rm --network tirenn-net --env-file .env -v .:/app multi-agent-researcher:latest python main.py

clean:
	@echo Cleaning temporary files...
	-rmdir /s /q __pycache__ 2>nul
	-rmdir /s /q .pytest_cache 2>nul
	-del /f /q latest_research_report.md 2>nul
