# Plex Auto-Prune Daemon - Makefile
.PHONY: help build test start stop logs clean

# Default target
help:
	@echo "Plex Auto-Prune Daemon - Available commands:"
	@echo ""
	@echo "  build    - Build the Docker image"
	@echo "  test     - Run configuration tests"
	@echo "  start    - Start the daemon in background"
	@echo "  stop     - Stop the daemon"
	@echo "  restart  - Restart the daemon"
	@echo "  logs     - Show daemon logs (follow mode)"
	@echo "  status   - Show container status"
	@echo "  clean    - Remove containers and images"
	@echo "  shell    - Open shell in running container"
	@echo ""

# Build the Docker image
build:
	docker compose build

# Run tests
test:
	@echo "🧪 Running configuration tests..."
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Copy .env.example and configure it first."; \
		exit 1; \
	fi
	docker compose run --rm plex-autoprune-daemon python -c "from main import *; print('✅ Configuration OK')"

# Start the daemon
start:
	docker compose up -d
	@echo "✅ Daemon started. Use 'make logs' to view output."

# Stop the daemon
stop:
	docker compose down

# Restart the daemon
restart: stop start

# Show logs
logs:
	docker compose logs -f

# Show container status
status:
	docker compose ps

# Clean up
clean:
	docker compose down --rmi local --volumes --remove-orphans

# Open shell in running container
shell:
	docker compose exec plex-autoprune-daemon bash

# Quick development cycle
dev: build test start logs