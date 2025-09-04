# Makefile for Tiny Gateway
# Development and testing automation

.PHONY: help venv test-unit test-integration test-all docker-build docker-rebuild clean

# Default target
help:
	@echo "Available targets:"
	@echo "  venv              - Create/activate virtual environment using uv"
	@echo "  test-unit         - Run unit tests (excluding integration tests)"
	@echo "  test-integration  - Run integration tests only"
	@echo "  test-all          - Run all tests (unit + integration)"
	@echo "  docker-build      - Build Docker image"
	@echo "  docker-rebuild    - Rebuild Docker image (no cache)"
	@echo "  clean             - Clean up generated files and caches"

# Virtual environment setup
venv:
	@echo "Setting up virtual environment with uv..."
	uv sync
	@echo "Virtual environment ready!"

# Unit tests (exclude integration directory)
test-unit: venv
	@echo "Running unit tests..."
	uv run pytest tests/ --ignore=tests/integration/ -v

# Integration tests only
test-integration: venv
	@echo "Running integration tests..."
	uv run pytest tests/integration/ -v

# All tests
test-all: venv
	@echo "Running all tests..."
	uv run pytest tests/ -v

# Docker build
docker-build:
	@echo "Building Docker image..."
	docker build -t tiny-gateway:latest .

# Docker rebuild (no cache)
docker-rebuild:
	@echo "Rebuilding Docker image (no cache)..."
	docker build --no-cache -t tiny-gateway:latest .

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	@echo "Cleanup complete!"
