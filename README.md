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
           ┌────────────────────────────┼─────────────────────────┐
           │                            │                          │
    ┌──────┴──────┐             ┌───────┴──────┐          ┌───────┴──────┐
    │    Spark    │             │    Trino     │          │  PyIceberg   │
    │  (catalog:  │             │  (catalog:   │          │    (REST     │
    │ gravitino   │             │   iceberg)   │          │   catalog)   │
    │   _irc)     │             │              │          │              │
    └─────────────┘             └──────────────┘          └─────┬────────┘
                                                                 │ metadata lookup
                                                          ┌──────┴────────┐
                                                          │    DuckDB     │
                                                          │ (reads from   │
                                                          │  S3 directly) │
                                                          └───────────────┘
           │                            │                          │
           └────────────────────────────┼─────────────────────────┘
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

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Minimum **8 GB RAM** allocated to Docker
- Minimum **4 CPU cores** recommended
- Ports free: `8080`, `8090`, `8888`, `9000`, `9001`, `9002`, `3306`

## Quick Start

```bash
# Clone and start
git clone https://github.com/<your-org>/gravitino-irc-quickstart
cd gravitino-irc-quickstart

# Copy and review environment config (credentials, ports)
cp .env.example .env

# Build images and start all services (~3-5 min first run)
make up

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
make duckdb-demo       # DuckDB → reads tables created above
```

### Validate cross-engine visibility
```bash
make validate
```
This confirms that tables written by one engine are readable by all others —
the core value-prop of the shared IRC catalog.

### Interactive shells

```bash
make spark-sql         # Spark SQL REPL (gravitino_irc catalog pre-loaded)
make spark-shell       # Spark Scala REPL
make spark-pyspark     # PySpark Python REPL
make trino-shell       # Trino CLI (iceberg catalog pre-loaded)
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
Catalog name: **`iceberg`**
```
connector.name            = iceberg
iceberg.catalog.type      = rest
iceberg.rest-catalog.uri  = http://gravitino-irc:9001/iceberg
```
Config: `conf/trino/catalog/iceberg.properties`

### PyIceberg
```python
catalog = load_catalog("gravitino_irc", **{
    "type": "rest",
    "uri": "http://gravitino-irc:9001/iceberg",
})
```

### DuckDB
DuckDB does not yet have a native IRC client. This quickstart uses PyIceberg to
resolve table metadata locations, then passes those paths to DuckDB's
`iceberg_scan()` function. DuckDB reads Iceberg data files directly from MinIO.

## IRC Configuration (Gravitino Iceberg REST Server)

The IRC is configured at `conf/gravitino-irc/gravitino-iceberg-rest-server.conf`:

| Setting | Value |
|---------|-------|
| Catalog backend | JDBC (MySQL) |
| JDBC URL | `jdbc:mysql://mysql:3306/iceberg_catalog` |
| Object store | MinIO (S3-compatible) |
| Warehouse | `s3://warehouse/` |
| Port | `9001` |

The custom Dockerfile (`dockerfiles/Dockerfile.irc`) adds the MySQL JDBC driver
to the upstream `apache/gravitino-iceberg-rest:latest` image, which doesn't
bundle it by default.

## Directory Structure

```
gravitino-irc-quickstart/
├── docker-compose.yml              # All services
├── .env                            # Editable config (ports, credentials)
├── Makefile                        # Convenience targets
├── dockerfiles/
│   ├── Dockerfile.irc              # Gravitino IRC + MySQL JDBC driver
│   ├── Dockerfile.spark            # Spark + Iceberg JARs + AWS bundle
│   └── Dockerfile.python           # PyIceberg + DuckDB + Jupyter
├── conf/
│   ├── gravitino-irc/
│   │   └── gravitino-iceberg-rest-server.conf   # IRC backend config
│   ├── spark/
│   │   └── spark-defaults.conf     # IRC catalog, S3 settings
│   └── trino/
│       ├── config.properties
│       ├── jvm.config
│       └── catalog/
│           └── iceberg.properties  # Trino → IRC via REST
├── scripts/
│   ├── init/
│   │   └── minio-init.sh           # MinIO bucket setup
│   ├── spark/
│   │   ├── irc_demo.py             # PySpark demo (submitted via spark-submit)
│   │   └── irc_shell_demo.sql      # Spark SQL reference script
│   ├── trino/
│   │   └── irc_demo.sql            # Trino demo SQL
│   ├── pyiceberg/
│   │   ├── irc_demo.py             # PyIceberg CRUD + schema evolution demo
│   │   └── validate_cross_engine.py # Cross-engine visibility validator
│   └── duckdb/
│       └── irc_demo.py             # DuckDB via PyIceberg metadata resolution
└── notebooks/
    └── 01_irc_exploration.ipynb    # Interactive Jupyter exploration
```

## Troubleshooting

**IRC won't start / exits immediately**
```bash
make logs-irc
```
Most common cause: MySQL not ready yet. The IRC container waits for the
`mysql` health check, but MySQL can take up to 30s to initialize on first run.
`make restart-irc` after MySQL is healthy usually fixes this.

**`jdbc-initialize` failure on MySQL**
The IRC tries to create Iceberg metadata tables in MySQL. If you see a
`Table already exists` error, the DB was initialized previously.
This is harmless — subsequent starts skip initialization.

**S3 / MinIO `NoSuchBucket` errors**
The `minio-setup` container creates the `warehouse` bucket on startup.
If it failed, run: `docker compose run --rm minio-setup`

**Spark `ClassNotFoundException` for Iceberg**
The Iceberg JARs are baked into the custom Spark image. Run `make build`
to rebuild if the image was pulled without building.

**DuckDB `iceberg_scan` fails**
DuckDB needs the metadata file path, not the table location. The demo
script resolves this via PyIceberg. Ensure `make pyiceberg-demo` has
run first so there's at least one table to scan.

**Port conflicts**
Edit `.env` to change any port, then `make down && make up`.

## Known Limitations

- **DuckDB Iceberg REST**: DuckDB does not natively speak the Iceberg REST protocol.
  The workaround (PyIceberg metadata lookup → `iceberg_scan`) is stable but adds a
  resolution step. Watch [duckdb/duckdb_iceberg](https://github.com/duckdb/duckdb_iceberg)
  for native REST catalog support.

- **IRC `jdbc-initialize` + multiple instances**: Setting `jdbc-initialize=true`
  with multiple IRC replicas may cause race conditions on first boot. For multi-node
  testing, initialize manually and set `jdbc-initialize=false`.

- **Gravitino IRC version**: Pinned to `latest` tag. Rebuild with `make build`
  when upstream releases new versions to pick up fixes.

## Contributing

PRs welcome. Please file issues for:
- Config bugs (wrong property names, version incompatibilities)
- New engine integrations (Flink, StarRocks, etc.)
- New test scenarios (schema evolution, MERGE, time travel)

## License

Apache License 2.0
