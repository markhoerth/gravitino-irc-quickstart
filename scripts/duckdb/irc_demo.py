"""
DuckDB IRC Demo — Gravitino Quickstart
=======================================
DuckDB has no native Iceberg REST catalog client (as of 1.x), so we use
two complementary approaches:

  A) DuckDB reads Iceberg table files directly from MinIO (S3 scan).
     DuckDB knows the table location from PyIceberg's catalog lookup,
     then uses its Iceberg extension to read the actual files.

  B) DuckDB queries via MotherDuck / httpfs for S3 paths directly —
     useful once you know a table's location.

This demo:
  1. Uses PyIceberg to look up table metadata from Gravitino IRC.
  2. Passes the resolved S3 metadata location to DuckDB's read_iceberg().
  3. Runs analytics queries entirely within DuckDB's engine.

Run:  make duckdb-demo
Or:   docker exec python-runner python3 /app/duckdb/irc_demo.py

Why this approach?
  DuckDB's iceberg extension reads Iceberg metadata files directly from S3.
  It does not speak the Iceberg REST protocol natively yet, so we bridge via
  PyIceberg to resolve the current snapshot's metadata.json path.

  This is the correct production pattern for DuckDB + Iceberg REST today.
  Watch: https://github.com/duckdb/duckdb_iceberg for native REST support.
"""

import os
import duckdb
from pyiceberg.catalog import load_catalog
from rich import print as rprint

IRC_URI    = os.environ.get("IRC_URI", "http://gravitino-irc:9001/iceberg")
S3_ENDPOINT = "http://minio:9000"
S3_KEY      = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
S3_SECRET   = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin123")

print("\n" + "="*60)
print("  Gravitino IRC — DuckDB Demo")
print("="*60)
print(f"  IRC endpoint : {IRC_URI}")
print(f"  S3 endpoint  : {S3_ENDPOINT}\n")

# ─── 1. Connect to Gravitino IRC via PyIceberg to resolve metadata ────────────
print("[1] Resolving table metadata via PyIceberg REST catalog ...")
catalog = load_catalog(
    "gravitino_irc",
    **{
        "type": "rest",
        "uri": IRC_URI,
        "s3.endpoint": S3_ENDPOINT,
        "s3.access-key-id": S3_KEY,
        "s3.secret-access-key": S3_SECRET,
        "s3.path-style-access": "true",
        "s3.region": "us-east-1",
    }
)

# List what's available
print("  Available namespaces:")
for ns in catalog.list_namespaces():
    print(f"    • {'.'.join(ns)}")
    for tbl in catalog.list_tables(ns):
        print(f"        └─ {'.'.join(tbl)}")

# ─── 2. Resolve metadata.json location for a target table ─────────────────────
# We look for tables created by the Spark or PyIceberg demos.
# Adjust NAMESPACE/TABLE_NAME if you created different ones first.
CANDIDATES = [
    ("demo_pyiceberg", "customers"),
    ("demo_spark",     "sales"),
    ("demo_trino",     "orders"),
]

target_table = None
target_meta  = None

for ns, tbl in CANDIDATES:
    try:
        iceberg_table = catalog.load_table((ns, tbl))
        # Get the current metadata file path (the one DuckDB needs)
        current_snapshot = iceberg_table.current_snapshot()
        if current_snapshot is None:
            print(f"  ⚠ {ns}.{tbl} exists but has no snapshots yet — skipping")
            continue
        metadata_location = iceberg_table.metadata_location
        target_table = f"{ns}.{tbl}"
        target_meta  = metadata_location
        print(f"\n  ✓ Found table: {target_table}")
        print(f"    Metadata location: {target_meta}")
        print(f"    Snapshot ID:       {current_snapshot.snapshot_id}")
        break
    except Exception:
        continue

if target_table is None:
    print("\n  ⚠ No tables found from demo candidates.")
    print("  Run 'make spark-demo' or 'make pyiceberg-demo' first, then re-run this script.")
    raise SystemExit(1)

# ─── 3. Configure DuckDB with S3/MinIO credentials ───────────────────────────
print("\n[3] Configuring DuckDB with MinIO S3 settings ...")
conn = duckdb.connect()

conn.execute("INSTALL iceberg; LOAD iceberg;")
conn.execute("INSTALL httpfs; LOAD httpfs;")

conn.execute(f"""
    CREATE OR REPLACE SECRET minio_secret (
        TYPE        s3,
        KEY_ID      '{S3_KEY}',
        SECRET      '{S3_SECRET}',
        ENDPOINT    '{S3_ENDPOINT.replace("http://", "")}',
        URL_STYLE   'path',
        USE_SSL     false,
        REGION      'us-east-1'
    );
""")

print("  ✓ DuckDB configured with MinIO credentials")

# ─── 4. Read Iceberg Table from MinIO via DuckDB ─────────────────────────────
print(f"\n[4] Reading {target_table} via DuckDB Iceberg extension ...")
print(f"    Metadata: {target_meta}\n")

# DuckDB iceberg_scan reads the table from the metadata file
# allowing_moved_paths=true handles local vs container path differences
try:
    result = conn.execute(f"""
        SELECT *
        FROM iceberg_scan('{target_meta}')
        LIMIT 10
    """).fetchdf()

    print(f"  ✓ Read {len(result)} rows\n")
    print(result.to_string(index=False))

except Exception as e:
    print(f"  ⚠ iceberg_scan failed: {e}")
    print("  Falling back to direct parquet scan ...")

    # Fallback: scan parquet files directly from MinIO
    table_location = iceberg_table.location()
    result = conn.execute(f"""
        SELECT *
        FROM read_parquet('{table_location}/data/**/*.parquet', hive_partitioning=true, union_by_name=true)
        LIMIT 10
    """).fetchdf()
    print(f"  ✓ Parquet fallback read {len(result)} rows\n")
    print(result.to_string(index=False))

# ─── 5. Analytics Queries in DuckDB ──────────────────────────────────────────
print(f"\n[5] Running analytics queries in DuckDB ...")

# Register as a DuckDB view for clean SQL syntax
conn.execute(f"""
    CREATE OR REPLACE VIEW iceberg_data AS
    SELECT * FROM iceberg_scan('{target_meta}')
""")

# Basic stats
print("\n  Row count:")
print(conn.execute("SELECT COUNT(*) AS row_count FROM iceberg_data").fetchdf().to_string(index=False))

# Column names
print("\n  Schema:")
schema_df = conn.execute("DESCRIBE iceberg_data").fetchdf()
print(schema_df[["column_name", "column_type"]].to_string(index=False))

# Summary stats on numeric columns
print("\n  Summary statistics:")
print(conn.execute("SUMMARIZE iceberg_data").fetchdf().to_string(index=False))

# ─── 6. Cross-table Join (if multiple demos have run) ────────────────────────
print(f"\n[6] DuckDB can join across Iceberg tables in the same IRC ...")
print("  (This works once multiple demo tables exist)")
print("  Example:")
print("    SELECT s.product, o.status, s.amount")
print("    FROM spark_view s JOIN trino_view o ON s.sale_date = o.order_date")
print("  Run individual demos first, then explore joins in Jupyter.\n")

# ─── 7. DuckDB In-Memory Table Creation ──────────────────────────────────────
print("[7] Creating an in-memory DuckDB table from Iceberg data ...")
conn.execute("""
    CREATE OR REPLACE TABLE local_analysis AS
    SELECT * FROM iceberg_data
""")
count = conn.execute("SELECT COUNT(*) FROM local_analysis").fetchone()[0]
print(f"  ✓ In-memory table created with {count} rows")
print("  You can now run arbitrary DuckDB SQL on local_analysis without re-reading S3.\n")

print("✓ DuckDB IRC demo complete\n")
conn.close()
