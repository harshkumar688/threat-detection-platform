# =============================================================================
# AI-Based Real-Time Threat Detection Platform
# =============================================================================
# Common development commands. Use: make <target>
# On Windows without make, use the equivalent docker-compose commands directly.

.PHONY: help setup up down restart logs test clean

help: ## Show available commands
	@echo.
	@echo   THREAT DETECTION PLATFORM - Development Commands
	@echo   ================================================
	@echo.
	@echo   Setup:
	@echo     make setup       - First-time setup (copy .env, build images)
	@echo.
	@echo   Docker:
	@echo     make up          - Start all services
	@echo     make down        - Stop all services
	@echo     make restart     - Restart all services
	@echo     make logs        - Tail all service logs
	@echo     make logs-back   - Tail backend logs only
	@echo     make ps          - Show running containers
	@echo.
	@echo   Testing:
	@echo     make test-back   - Run backend tests
	@echo.
	@echo   Cleanup:
	@echo     make clean       - Stop services and remove volumes
	@echo.

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup: ## First-time project setup
	@if not exist .env copy .env.example .env
	docker-compose build

# ---------------------------------------------------------------------------
# Docker Operations
# ---------------------------------------------------------------------------
up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

restart: ## Restart all services
	docker-compose restart

logs: ## Tail all logs
	docker-compose logs -f

logs-back: ## Tail backend logs
	docker-compose logs -f backend

ps: ## Show running containers
	docker-compose ps

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test-back: ## Run backend tests
	docker-compose exec backend pytest tests/ -v

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove containers, volumes, images
	docker-compose down -v --rmi local
