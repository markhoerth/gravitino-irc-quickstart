# Gravitino IRC Multi-Engine Quickstart

Tests the [Apache Gravitino](https://gravitino.apache.org/) Iceberg REST Catalog (IRC)
across four client engines: **Spark**, **Trino**, **DuckDB**, and **PyIceberg**.
All engines point directly at the IRC endpoint — not the Gravitino server API —
demonstrating IRC's interoperability as a pure Iceberg REST spec implementation.

## Architecture

```
                         ┌────────────────────────────────────┐
                         │   Gravitino Iceberg REST Catalog   │
                         │       http://localhost:9001        │
                         │   (IRC — spec endpoint /iceberg)   │
                         └──────────────┬─────────────────────┘
                                        │ Iceberg REST API
           ┌────────────────────────────┼──────────────────────────┐
           │                            │                           │
    ┌──────┴──────┐             ┌───────┴──────┐          ┌────────┴─────┐
    │    Spark    │             │    Trino     │          │  PyIceberg   │
    │  (catalog:  │             │  (catalog:   │          │    (REST     │
    │ gravitino   │             │  gravitino   │          │   catalog)   │
    │   _irc)     │             │    _irc)     │          │              │
    └─────────────┘             └──────────────┘          └──────────────┘
                                                          ┌──────────────┐
                                                          │    DuckDB    │
                                                          │  (ATTACH via │
                                                          │  IRC REST)   │
                                                          └──────────────┘
           │                            │                          │
           └────────────────────────────┼──────────────────────────┘
                                        │ S3 FileIO
                                 ┌──────┴──────┐
                                 │    MinIO    │
                                 │  warehouse  │
                                 │  (s3://     │
                                 │  warehouse) │
                                 └──────┬──────┘
                                        │ JDBC metadata
                                 ┌──────┴──────┐
                                 │    MySQL    │
                                 │  (Iceberg   │
                                 │  meta tables│
                                 └─────────────┘

┌──────────────────────┐
│  Gravitino Server    │  ← UI only (not in query path)
│  http://localhost:8090│    used for catalog management
└──────────────────────┘
```

### Key design decision
Engines connect to the IRC REST endpoint (`http://gravitino-irc:9001/iceberg`) directly,
**not** through the Gravitino server API (`http://gravitino:8090`). The Gravitino server
is included for its UI and metalake management, but is not in the query path.

All four engines use the catalog name **`gravitino_irc`** — this is intentional and
required for cross-engine view portability (see [Cross-Engine Views](#cross-engine-views)).

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Minimum **8 GB RAM** allocated to Docker
- Minimum **4 CPU cores** recommended
- Ports free: `8080`, `8090`, `8888`, `9000`, `9001`, `9002`, `3306`

## Quick Start

```bash
# Clone and start
git clone https://github.com/markhoerth/gravitino-irc-quickstart
cd gravitino-irc-quickstart

# Build images and start all services (~3-5 min first run)
docker compose up -d --build

# Wait for health checks to pass (~60s), then run all demos
make demo-all
```

## Services & URLs

| Service              | URL                                              | Notes                          |
|----------------------|--------------------------------------------------|--------------------------------|
| **Gravitino UI**     | http://localhost:8090                            | Catalog management UI          |
| **IRC REST API**     | http://localhost:9001/iceberg                    | Iceberg REST catalog endpoint  |
| **Trino UI**         | http://localhost:8080                            | Query history, cluster status  |
| **Jupyter**          | http://localhost:8888                            | PyIceberg + DuckDB notebooks   |
| **MinIO Console**    | http://localhost:9002                            | Browse data files in S3        |
| **MySQL**            | localhost:3306                                   | Iceberg metadata store         |

MinIO credentials: `minioadmin` / `minioadmin123`

## Running the Demos

### Individual engine demos

```bash
make spark-demo        # Spark → creates demo_spark.sales
make trino-demo        # Trino → creates demo_trino.orders
make pyiceberg-demo    # PyIceberg → creates demo_pyiceberg.customers
make duckdb-demo       # DuckDB → full read/write via native IRC ATTACH
```

### Validate cross-engine visibility
```bash
make validate
```
Confirms that tables written by one engine are readable by all others —
the core value-prop of the shared IRC catalog.

### Interactive shells

```bash
make spark-sql         # Spark SQL REPL (gravitino_irc catalog pre-loaded)
make spark-shell       # Spark Scala REPL
make spark-pyspark     # PySpark Python REPL
make trino-shell       # Trino CLI (gravitino_irc catalog pre-loaded)
make duckdb-shell      # DuckDB interactive SQL shell
```

### Jupyter Notebook
Open http://localhost:8888 and navigate to `notebooks/01_irc_exploration.ipynb`.
No token required in dev mode.

## Catalog Configuration per Engine

### Spark
Catalog name: **`gravitino_irc`**
```
spark.sql.catalog.gravitino_irc         = org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.gravitino_irc.type    = rest
spark.sql.catalog.gravitino_irc.uri     = http://gravitino-irc:9001/iceberg
```
Config: `conf/spark/spark-defaults.conf`

### Trino
Catalog name: **`gravitino_irc`** (derived from filename `gravitino_irc.properties`)
```
connector.name            = iceberg
iceberg.catalog.type      = rest
iceberg.rest-catalog.uri  = http://gravitino-irc:9001/iceberg
```
Config: `conf/trino/catalog/gravitino_irc.properties`

### PyIceberg
```python
catalog = load_catalog("gravitino_irc", **{
    "type": "rest",
    "uri": "http://gravitino-irc:9001/iceberg",
})
```

### DuckDB
DuckDB 1.4.x supports native IRC ATTACH — no metadata path lookups required:
```sql
ATTACH '' AS gravitino (
    TYPE               iceberg,
    ENDPOINT           'http://gravitino-irc:9001/iceberg',
    AUTHORIZATION_TYPE 'none'
);

SELECT * FROM gravitino.demo_spark.sales;
INSERT INTO gravitino.sandbox.test VALUES (1, 2);
```
DuckDB is a full read/write IRC citizen as of version 1.4.x.

## Cross-Engine Views

This quickstart demonstrates cross-engine Iceberg view portability — a capability
that requires all engines to share the same catalog name.

### How it works

When an engine creates a view via the IRC, the Iceberg view spec stores the SQL
along with a `default-catalog` field identifying the creating engine's catalog name.
When another engine reads that view, it uses `default-catalog` to resolve unqualified
table references in the view SQL.

**This means all engines must use the same catalog name** for views to be portable.
In this quickstart, all engines use `gravitino_irc`.

### Cross-engine view matrix

| View created by | Readable by Spark | Readable by Trino | Readable by DuckDB |
|----------------|:-----------------:|:-----------------:|:-----------------:|
| **Spark**      | ✅ | ❌ dialect rejection | ❌ not supported |
| **Trino**      | ✅ same catalog name | ✅ | ❌ not supported |
| **PyIceberg**  | ✅ | ✅ | ❌ not supported |

**Trino → Spark view example:**
```sql
-- In Trino shell
USE gravitino_irc.sandbox;
CREATE VIEW my_view AS SELECT * FROM test WHERE x > 1;
```
```sql
-- In Spark SQL — works because both use catalog name 'gravitino_irc'
SELECT * FROM sandbox.my_view;
```

**Why Spark → Trino fails:** Trino enforces strict dialect checking and refuses
to execute view SQL tagged with the `spark` dialect. There is currently no
configuration property to override this in Trino 480.

**Why DuckDB doesn't support views:** DuckDB's IRC ATTACH implementation
(1.4.x) supports tables but not views. This is expected to improve in future releases.

## IRC Configuration (Gravitino Iceberg REST Server)

The IRC is configured via environment variables in `docker-compose.yml`.
The startup script `rewrite_config.py` translates `GRAVITINO_*` environment
variables into the server's configuration file at startup.

**Important:** Do not mount a config file directly into the IRC container.
The startup script rewrites the config file on every boot — a read-only
bind mount will cause the container to fail.

| Setting | Value |
|---------|-------|
| Catalog backend | JDBC (MySQL) |
| JDBC URL | `jdbc:mysql://mysql:3306/iceberg_catalog` |
| Object store | MinIO (S3-compatible) |
| Warehouse | `s3://warehouse/` |
| Port | `9001` |
| Credential provider | `s3-secret-key` (required for table creation) |

The custom Dockerfile (`dockerfiles/Dockerfile.irc`) adds the MySQL JDBC driver
to the upstream `apache/gravitino-iceberg-rest:latest` image. The driver must be
placed in `/root/gravitino-iceberg-rest-server/libs/` — not `/opt/gravitino/libs/`.

## Directory Structure

```
gravitino-irc-quickstart/
├── docker-compose.yml              # All services
├── .env.example                    # Template config (copy to .env)
├── Makefile                        # Convenience targets
├── dockerfiles/
│   ├── Dockerfile.irc              # Gravitino IRC + MySQL JDBC driver
│   ├── Dockerfile.spark            # Spark + Iceberg JARs + AWS SDK v2
│   └── Dockerfile.python           # PyIceberg + DuckDB 1.4.x + Jupyter
├── conf/
│   ├── gravitino-irc/
│   │   └── gravitino-iceberg-rest-server.conf   # Reference only (not mounted)
│   ├── spark/
│   │   └── spark-defaults.conf     # IRC catalog, S3 settings
│   └── trino/
│       ├── config.properties
│       ├── jvm.config
│       ├── node.properties
│       └── catalog/
│           └── gravitino_irc.properties  # Trino → IRC via REST
├── scripts/
│   ├── init/
│   │   └── minio-init.sh           # MinIO bucket setup
│   ├── spark/
│   │   ├── irc_demo.py             # PySpark demo
│   │   └── irc_shell_demo.sql      # Spark SQL reference
│   ├── trino/
│   │   └── irc_demo.sql            # Trino demo SQL
│   ├── pyiceberg/
│   │   ├── irc_demo.py             # PyIceberg CRUD + schema evolution
│   │   └── validate_cross_engine.py # Cross-engine visibility validator
│   └── duckdb/
│       └── irc_demo.py             # DuckDB native ATTACH demo
└── notebooks/
    └── 01_irc_exploration.ipynb    # Interactive Jupyter exploration
```

## Troubleshooting

**IRC won't start — `OSError: [Errno 16] Device or resource busy`**

Do not mount a config file into the IRC container. The startup script
`rewrite_config.py` tries to delete and rewrite the config file on every
boot. A read-only bind mount prevents this. Configure the IRC using
environment variables in `docker-compose.yml` instead.

**IRC starts but MySQL driver not found**

The MySQL JDBC driver must be in `/root/gravitino-iceberg-rest-server/libs/`.
Check `dockerfiles/Dockerfile.irc` — the `GRAVITINO_IRC_LIBS` path must match
the actual server directory, not `/opt/gravitino/libs/`.

**`jdbc-initialize` failure on MySQL**

The IRC creates Iceberg metadata tables in MySQL on first boot. A
`Table already exists` error on subsequent starts is harmless.

**S3 / MinIO `NoSuchBucket` errors**

The `minio-setup` container creates the `warehouse` bucket on startup.
If it failed: `docker compose run --rm minio-setup`

**Trino crash-loops on startup**

Check `docker compose logs trino` for defunct properties. Known removed
properties in current Trino versions:
- `query.max-total-memory-per-node` — removed, use `query.max-memory-per-node`
- `iceberg.pushdown-filter-enabled` — removed
- `iceberg.view-unknown-dialects-read.enabled` — does not exist

**WSL2: `restart` fails with bind mount error**

On WSL2 + Docker Desktop, `docker compose restart <service>` fails when
bind-mounted config files have been edited. Always use
`docker compose down && docker compose up -d` instead.

**Trino `still initializing` for several minutes**

Normal on WSL2. Trino can take 3-5 minutes to fully initialize after the
health check passes. Keep retrying `make trino-shell` every 30 seconds.

**Port conflicts**

Edit `.env` (copied from `.env.example`) to remap any port, then
`docker compose down && docker compose up -d`.

## Known Limitations

- **Cross-engine views (Spark → Trino):** Trino refuses to execute view SQL
  tagged with the `spark` dialect. No configuration override exists in Trino 480.
  Trino-created views are readable by Spark when both use the same catalog name.

- **DuckDB views:** DuckDB's IRC ATTACH does not yet expose Iceberg views.
  Tables are fully supported for read and write.

- **IRC `jdbc-initialize` + multiple instances:** With multiple IRC replicas,
  set `jdbc-initialize=false` after first boot and initialize the schema manually.

- **Gravitino IRC pinned to `latest`:** Rebuild with `make build` when upstream
  releases new versions. The MySQL JDBC driver version in `Dockerfile.irc` may
  need updating for new MySQL server versions.

## Contributing

PRs welcome. Please file issues for:
- Config bugs (wrong property names, version incompatibilities)
- New engine integrations (Flink, StarRocks, etc.)
- New test scenarios (schema evolution, MERGE, time travel)

## License

Apache License 2.0
