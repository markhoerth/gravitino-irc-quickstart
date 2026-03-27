###############################################################################
# Gravitino IRC Multi-Engine Quickstart — Makefile
# Usage: make <target>
###############################################################################

.DEFAULT_GOAL := help
COMPOSE       := docker compose
PROJECT       := gravitino-irc

# ── Colours ───────────────────────────────────────────────────────────────────
BOLD  := $(shell tput bold 2>/dev/null || echo '')
RESET := $(shell tput sgr0 2>/dev/null || echo '')
GREEN := $(shell tput setaf 2 2>/dev/null || echo '')
CYAN  := $(shell tput setaf 6 2>/dev/null || echo '')

# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: build
build: ## Build all custom Docker images (IRC, Spark, Python)
	@echo "$(BOLD)$(CYAN)Building images...$(RESET)"
	$(COMPOSE) build

.PHONY: up
up: ## Start all services (builds if needed)
	@echo "$(BOLD)$(CYAN)Starting Gravitino IRC environment...$(RESET)"
	$(COMPOSE) up -d --build
	@echo ""
	@echo "$(BOLD)$(GREEN)Services starting — wait ~60s for health checks$(RESET)"
	@echo ""
	@echo "  Gravitino UI   → http://localhost:8090"
	@echo "  IRC endpoint   → http://localhost:9001/iceberg/v1/config"
	@echo "  Trino UI       → http://localhost:8080"
	@echo "  Jupyter        → http://localhost:8888"
	@echo "  MinIO Console  → http://localhost:9002  (minioadmin / minioadmin123)"
	@echo ""

.PHONY: down
down: ## Stop all services (keeps volumes)
	$(COMPOSE) down

.PHONY: down-clean
down-clean: ## Stop and delete ALL data (volumes, images)
	@echo "$(BOLD)This will delete all data volumes. Are you sure? [y/N]$(RESET)" && \
	  read ans && [ $${ans:-N} = y ]
	$(COMPOSE) down --volumes --remove-orphans
	docker image rm gravitino-irc-custom gravitino-spark-custom gravitino-python-custom 2>/dev/null || true

.PHONY: restart
restart: ## Restart all services
	$(COMPOSE) restart

.PHONY: restart-irc
restart-irc: ## Restart only the Gravitino IRC service
	$(COMPOSE) restart gravitino-irc

.PHONY: status
status: ## Show service health and port bindings
	@$(COMPOSE) ps

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: logs-irc
logs-irc: ## Tail Gravitino IRC logs
	$(COMPOSE) logs -f gravitino-irc

.PHONY: logs-spark
logs-spark: ## Tail Spark logs
	$(COMPOSE) logs -f spark

.PHONY: logs-trino
logs-trino: ## Tail Trino logs
	$(COMPOSE) logs -f trino

# ─────────────────────────────────────────────────────────────────────────────
# Spark
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: spark-sql
spark-sql: ## Open interactive Spark SQL shell (directly against IRC)
	@echo "$(BOLD)$(CYAN)Opening Spark SQL shell — catalog: gravitino_irc$(RESET)"
	@echo "  Tip: run 'SHOW NAMESPACES;' to get started\n"
	$(COMPOSE) exec spark spark-sql \
	  --conf spark.sql.defaultCatalog=gravitino_irc

.PHONY: spark-shell
spark-shell: ## Open Spark Scala REPL
	$(COMPOSE) exec spark spark-shell

.PHONY: spark-pyspark
spark-pyspark: ## Open PySpark Python REPL
	$(COMPOSE) exec spark pyspark

.PHONY: spark-demo
spark-demo: ## Run the Spark IRC demo script (creates demo_spark.sales)
	@echo "$(BOLD)$(CYAN)Running Spark IRC demo...$(RESET)"
	$(COMPOSE) exec spark spark-submit /scripts/irc_demo.py

.PHONY: spark-sql-demo
spark-sql-demo: ## Run the Spark SQL demo script interactively
	$(COMPOSE) exec spark spark-sql -f /scripts/irc_shell_demo.sql

# ─────────────────────────────────────────────────────────────────────────────
# Trino
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: trino-shell
trino-shell: ## Open Trino CLI shell (catalog: iceberg → Gravitino IRC)
	@echo "$(BOLD)$(CYAN)Opening Trino CLI — catalog: iceberg$(RESET)"
	@echo "  Tip: run 'SHOW SCHEMAS FROM iceberg;' to get started\n"
	$(COMPOSE) exec trino trino \
	  --server http://localhost:8080 \
	  --catalog iceberg

.PHONY: trino-demo
trino-demo: ## Run the Trino IRC demo SQL (creates demo_trino.orders)
	@echo "$(BOLD)$(CYAN)Running Trino IRC demo...$(RESET)"
	$(COMPOSE) exec trino trino \
	  --server http://localhost:8080 \
	  --catalog iceberg \
	  --file /scripts/irc_demo.sql

# ─────────────────────────────────────────────────────────────────────────────
# PyIceberg + DuckDB (python-runner container)
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: pyiceberg-demo
pyiceberg-demo: ## Run PyIceberg IRC demo (creates demo_pyiceberg.customers)
	@echo "$(BOLD)$(CYAN)Running PyIceberg IRC demo...$(RESET)"
	$(COMPOSE) exec python-runner python3 /app/pyiceberg/irc_demo.py

.PHONY: duckdb-demo
duckdb-demo: ## Run DuckDB IRC demo (reads Iceberg tables from MinIO)
	@echo "$(BOLD)$(CYAN)Running DuckDB IRC demo...$(RESET)"
	@echo "  Note: requires at least one other demo to have run first.\n"

.PHONY: duckdb-shell
duckdb-shell: ## Open DuckDB interactive SQL shell (in python-runner container)
	@echo "$(BOLD)$(CYAN)Opening DuckDB shell...$(RESET)"
	@echo "  Tip: INSTALL iceberg; LOAD iceberg; then iceberg_scan() to query tables\n"
	$(COMPOSE) exec python-runner duckdb

.PHONY: validate
validate: ## Cross-engine validation: confirms all engines share the same IRC catalog
	@echo "$(BOLD)$(CYAN)Running cross-engine validation...$(RESET)"
	$(COMPOSE) exec python-runner python3 /app/pyiceberg/validate_cross_engine.py

# ─────────────────────────────────────────────────────────────────────────────
# All demos in sequence
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: demo-all
demo-all: spark-demo trino-demo pyiceberg-demo duckdb-demo validate ## Run ALL demos in sequence, then validate
	@echo "$(BOLD)$(GREEN)✓ All demos complete. Cross-engine validation passed.$(RESET)"

# ─────────────────────────────────────────────────────────────────────────────
# IRC / Gravitino API
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: irc-health
irc-health: ## Check Gravitino IRC health endpoint
	@curl -sf http://localhost:9001/iceberg/v1/config | python3 -m json.tool

.PHONY: irc-namespaces
irc-namespaces: ## List namespaces in the IRC via REST API
	@curl -sf http://localhost:9001/iceberg/v1/namespaces | python3 -m json.tool

.PHONY: irc-tables
irc-tables: ## List tables in a namespace (NAMESPACE=demo_spark)
	@NAMESPACE=$${NAMESPACE:-demo_spark}; \
	  curl -sf "http://localhost:9001/iceberg/v1/namespaces/$${NAMESPACE}/tables" | python3 -m json.tool

.PHONY: gravitino-health
gravitino-health: ## Check Gravitino server API health
	@curl -sf http://localhost:8090/api/version | python3 -m json.tool

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: minio-ls
minio-ls: ## List MinIO warehouse bucket contents
	$(COMPOSE) exec minio-setup mc ls minio/warehouse --recursive || \
	  docker run --rm --network $(PROJECT)_irc-net minio/mc \
	    --no-color alias set m http://minio:9000 minioadmin minioadmin123 \&\& mc ls m/warehouse

.PHONY: mysql-shell
mysql-shell: ## Open MySQL shell (view Iceberg catalog tables)
	$(COMPOSE) exec mysql mysql \
	  -u iceberg -piceberg_password iceberg_catalog

.PHONY: pull
pull: ## Pull latest upstream images
	$(COMPOSE) pull

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "$(BOLD)Gravitino IRC Multi-Engine Quickstart$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
