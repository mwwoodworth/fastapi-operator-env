.PHONY: help build run test deploy clean logs

# Default target
help:
	@echo "BrainOps FastAPI Operator Environment - Make Commands"
	@echo ""
	@echo "Development:"
	@echo "  make build          - Build Docker image"
	@echo "  make run            - Run locally with docker-compose"
	@echo "  make test           - Run tests"
	@echo "  make logs           - View logs"
	@echo "  make clean          - Clean up containers and volumes"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        - Run database migrations"
	@echo "  make migration      - Create new migration"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy-gcp     - Deploy to Google Cloud Run"
	@echo "  make deploy-vercel  - Deploy frontend to Vercel"
	@echo "  make deploy-all     - Deploy both backend and frontend"
	@echo ""
	@echo "Testing:"
	@echo "  make test-local     - Test local deployment"
	@echo "  make test-prod      - Test production deployment"
	@echo "  make lint           - Run code linting"
	@echo ""
	@echo "Utilities:"
	@echo "  make env            - Copy .env.master to .env"
	@echo "  make secrets        - Generate secret keys"

# Development commands
build:
	docker build -t brainops-fastapi:dev -f Dockerfile.production .

run:
	docker-compose up -d
	@echo "Services started. Access API at http://localhost:8000"

logs:
	docker-compose logs -f backend

clean:
	docker-compose down -v
	docker system prune -f

# Database commands
migrate:
	docker-compose run backend alembic upgrade head

migration:
	@read -p "Enter migration message: " msg; \
	docker-compose run backend alembic revision --autogenerate -m "$$msg"

# Testing commands
test:
	docker-compose run backend pytest tests/ -v

test-local:
	./test-deployment.sh http://localhost:8000

test-prod:
	@echo "Enter your Cloud Run URL:"
	@read url; ./test-deployment.sh $$url

lint:
	docker-compose run backend black apps/
	docker-compose run backend isort apps/
	docker-compose run backend flake8 apps/

# Deployment commands
deploy-gcp:
	./deploy-to-gcp.sh

deploy-vercel:
	./deploy-vercel-frontend.sh

deploy-all: deploy-gcp deploy-vercel
	@echo "Full deployment complete!"

# Utility commands
env:
	cp .env.master .env
	@echo ".env file created from .env.master"

secrets:
	@echo "Generating secret keys..."
	@echo "SECRET_KEY=$$(openssl rand -hex 32)"
	@echo "JWT_SECRET=$$(openssl rand -hex 32)"
	@echo "FERNET_SECRET=$$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

# Docker commands
docker-build-prod:
	docker build -t brainops-fastapi:latest -f Dockerfile.production .

docker-run-prod:
	docker run -p 8000:8000 --env-file .env.production brainops-fastapi:latest

# Git commands
commit:
	@read -p "Enter commit message: " msg; \
	git add -A && git commit -m "$$msg"

push:
	git push origin main

# Health check
health:
	@curl -s http://localhost:8000/healthz | jq '.' || echo "Service not running"

# View API docs
docs:
	@echo "Opening API documentation..."
	@python -m webbrowser http://localhost:8000/docs