"""
DuckDB IRC Demo — Gravitino Quickstart
=======================================
Demonstrates DuckDB as a full read/write IRC client using native ATTACH.
DuckDB 1.4.x supports the Iceberg REST catalog protocol directly — no
metadata path lookups, no PyIceberg bridge, just clean SQL.

Run:  make duckdb-demo
Or:   docker exec python-runner python3 /app/duckdb/irc_demo.py

DuckDB IRC capabilities (1.4.x):
  ✅ ATTACH to IRC via REST protocol
  ✅ SHOW ALL TABLES
  ✅ SELECT (read from any engine's tables)
  ✅ INSERT, CREATE TABLE, DROP TABLE
  ✅ Time travel (AT VERSION / AT TIMESTAMP)
  ❌ Views (not yet supported in DuckDB IRC client)
"""

import os
import duckdb

IRC_URI     = os.environ.get("IRC_URI", "http://gravitino-irc:9001/iceberg")
S3_ENDPOINT = "http://minio:9000"
S3_KEY      = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
S3_SECRET   = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin123")

print("\n" + "="*60)
print("  Gravitino IRC — DuckDB Demo")
print("="*60)
print(f"  IRC endpoint : {IRC_URI}")
print(f"  S3 endpoint  : {S3_ENDPOINT}\n")

# ─── 1. Connect and configure ─────────────────────────────────────────────────
print("[1] Connecting DuckDB to Gravitino IRC ...")
conn = duckdb.connect()

conn.execute("INSTALL iceberg; LOAD iceberg;")
conn.execute("INSTALL httpfs;  LOAD httpfs;")

# S3/MinIO credentials
conn.execute(f"""
    CREATE SECRET minio_secret (
        TYPE        s3,
        KEY_ID      '{S3_KEY}',
        SECRET      '{S3_SECRET}',
        ENDPOINT    '{S3_ENDPOINT.replace("http://", "")}',
        URL_STYLE   'path',
        USE_SSL     false,
        REGION      'us-east-1'
    );
""")

# Attach Gravitino IRC — no OAuth2, no warehouse name needed
conn.execute(f"""
    ATTACH '' AS gravitino (
        TYPE               iceberg,
        ENDPOINT           '{IRC_URI}',
        AUTHORIZATION_TYPE 'none'
    );
""")

print("  ✓ Connected — catalog alias: gravitino\n")

# ─── 2. Discover catalog contents ─────────────────────────────────────────────
print("[2] Discovering catalog contents ...")
tables = conn.execute("SHOW ALL TABLES").fetchdf()
print(f"  Tables visible ({len(tables)} total):")
for _, row in tables.iterrows():
    print(f"    • {row['database']}.{row['schema']}.{row['name']}")

# ─── 3. Cross-engine reads ────────────────────────────────────────────────────
print("\n[3] Cross-engine reads — tables written by Spark, Trino, PyIceberg ...")

for ns, tbl in [("demo_spark", "sales"), ("demo_trino", "orders"), ("demo_pyiceberg", "customers")]:
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM gravitino.{ns}.{tbl}").fetchone()[0]
        print(f"  ✓ gravitino.{ns}.{tbl}: {count} rows")
    except Exception as e:
        print(f"  ⚠ gravitino.{ns}.{tbl}: {e}")

# ─── 4. Analytics on Spark table ─────────────────────────────────────────────
print("\n[4] Analytics on demo_spark.sales ...")
result = conn.execute("""
    SELECT region, COUNT(*) AS orders, ROUND(SUM(amount), 2) AS revenue
    FROM gravitino.demo_spark.sales
    GROUP BY region
    ORDER BY revenue DESC
""").fetchdf()
print(result.to_string(index=False))

# ─── 5. Create a table from DuckDB ───────────────────────────────────────────
print("\n[5] Creating a new table from DuckDB ...")
conn.execute("DROP TABLE IF EXISTS gravitino.sandbox.duckdb_test")
conn.execute("""
    CREATE TABLE gravitino.sandbox.duckdb_test (
        id      INTEGER,
        engine  VARCHAR,
        note    VARCHAR
    )
""")
print("  ✓ Created gravitino.sandbox.duckdb_test")

# ─── 6. Write data from DuckDB ────────────────────────────────────────────────
print("\n[6] Inserting rows from DuckDB ...")
conn.execute("""
    INSERT INTO gravitino.sandbox.duckdb_test VALUES
        (1, 'DuckDB',    'Written by DuckDB 1.4.x via IRC'),
        (2, 'DuckDB',    'Full read/write IRC support'),
        (3, 'DuckDB',    'No metadata path lookup needed')
""")
result = conn.execute("SELECT * FROM gravitino.sandbox.duckdb_test").fetchdf()
print(f"  ✓ Wrote {len(result)} rows")
print(result.to_string(index=False))

# ─── 7. Cross-engine write verification ──────────────────────────────────────
print("\n[7] Inserting into sandbox.test (readable by Spark and Trino) ...")
current = conn.execute("SELECT MAX(x) FROM gravitino.sandbox.test").fetchone()[0]
next_x  = (current or 0) + 1
conn.execute(f"INSERT INTO gravitino.sandbox.test VALUES ({next_x}, {next_x + 1})")
count = conn.execute("SELECT COUNT(*) FROM gravitino.sandbox.test").fetchone()[0]
print(f"  ✓ Inserted row ({next_x}, {next_x+1}) — table now has {count} rows")
print("  → Verify in Trino:  SELECT * FROM iceberg.sandbox.test;")
print("  → Verify in Spark:  SELECT * FROM sandbox.test;")

# ─── 8. Time travel ───────────────────────────────────────────────────────────
print("\n[8] Time travel — snapshot history for sandbox.test ...")
try:
    snaps = conn.execute("""
        SELECT snapshot_id, timestamp_ms
        FROM iceberg_snapshots('gravitino.sandbox.test')
        ORDER BY timestamp_ms
    """).fetchdf()
    print(f"  {len(snaps)} snapshots found")
    if len(snaps) >= 2:
        first_snap = snaps.iloc[0]['snapshot_id']
        old = conn.execute(f"""
            SELECT COUNT(*) FROM gravitino.sandbox.test
            AT (VERSION => {first_snap})
        """).fetchone()[0]
        print(f"  Row count at first snapshot ({first_snap}): {old}")
        print(f"  Row count now: {count}")
except Exception as e:
    print(f"  ⚠ Time travel: {e}")

# ─── 9. Summary ───────────────────────────────────────────────────────────────
print("\n[9] Final catalog state ...")
final_tables = conn.execute("SHOW ALL TABLES").fetchdf()
for _, row in final_tables.iterrows():
    cnt = conn.execute(f"SELECT COUNT(*) FROM gravitino.{row['schema']}.{row['name']}").fetchone()[0]
    print(f"  {row['database']}.{row['schema']}.{row['name']}: {cnt} rows")

print("\n✓ DuckDB IRC demo complete\n")
conn.close()
