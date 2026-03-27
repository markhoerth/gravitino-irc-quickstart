"""
Spark IRC Demo — Gravitino Quickstart
======================================
Tests Spark's integration with the Gravitino Iceberg REST Catalog.

Run via:  make spark-demo
Or:       docker exec spark spark-submit /scripts/irc_demo.py

The catalog 'gravitino_irc' is pre-configured in spark-defaults.conf.
All operations hit the IRC directly — Gravitino server is not in the query path.
"""

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, DateType
from datetime import date

print("\n" + "="*60)
print("  Gravitino IRC — Spark Demo")
print("="*60 + "\n")

spark = SparkSession.builder \
    .appName("Gravitino IRC Spark Demo") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

CATALOG = "gravitino_irc"
SCHEMA  = "demo_spark"
TABLE   = "sales"

# ── 1. Namespace / Schema ─────────────────────────────────────────────────────
print(f"[1] Creating schema {CATALOG}.{SCHEMA} ...")
spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"SHOW NAMESPACES IN {CATALOG}").show()

# ── 2. Create Table ───────────────────────────────────────────────────────────
print(f"[2] Creating Iceberg table {CATALOG}.{SCHEMA}.{TABLE} ...")
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.{TABLE} (
        id        INT,
        product   STRING,
        region    STRING,
        amount    DOUBLE,
        sale_date DATE
    )
    USING iceberg
    PARTITIONED BY (region)
    TBLPROPERTIES (
        'write.format.default'       = 'parquet',
        'write.parquet.compression-codec' = 'zstd',
        'history.expire.min-snapshots-to-keep' = '3'
    )
""")

# ── 3. Insert Data ────────────────────────────────────────────────────────────
print("[3] Inserting sample rows ...")
spark.sql(f"""
    INSERT INTO {CATALOG}.{SCHEMA}.{TABLE} VALUES
      (1,  'Widget A',  'WEST',  1200.50, DATE '2024-01-15'),
      (2,  'Widget B',  'EAST',   890.00, DATE '2024-01-16'),
      (3,  'Gadget X',  'WEST',  3400.00, DATE '2024-02-01'),
      (4,  'Gadget Y',  'NORTH',  500.75, DATE '2024-02-14'),
      (5,  'Widget A',  'EAST',  2100.00, DATE '2024-03-01'),
      (6,  'Gadget Z',  'SOUTH', 1750.25, DATE '2024-03-15')
""")

# ── 4. Query ──────────────────────────────────────────────────────────────────
print("[4] Running SELECT query ...")
spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.{TABLE} ORDER BY sale_date").show()

print("[4b] Aggregation by region ...")
spark.sql(f"""
    SELECT region, COUNT(*) AS orders, ROUND(SUM(amount), 2) AS total_revenue
    FROM {CATALOG}.{SCHEMA}.{TABLE}
    GROUP BY region
    ORDER BY total_revenue DESC
""").show()

# ── 5. Schema Evolution ───────────────────────────────────────────────────────
print("[5] Iceberg schema evolution — adding 'discount' column ...")
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.{TABLE} ADD COLUMN discount DOUBLE")
spark.sql(f"INSERT INTO {CATALOG}.{SCHEMA}.{TABLE} VALUES (7, 'Widget C', 'WEST', 999.99, DATE '2024-04-01', 0.10)")
spark.sql(f"SELECT * FROM {CATALOG}.{SCHEMA}.{TABLE} WHERE id = 7").show()

# ── 6. Time Travel ────────────────────────────────────────────────────────────
print("[6] Iceberg snapshots (time travel) ...")
spark.sql(f"SELECT snapshot_id, committed_at, operation FROM {CATALOG}.{SCHEMA}.{TABLE}.snapshots").show(truncate=False)

# ── 7. Metadata Tables ────────────────────────────────────────────────────────
print("[7] Iceberg metadata — files ...")
spark.sql(f"SELECT file_path, record_count, file_size_in_bytes FROM {CATALOG}.{SCHEMA}.{TABLE}.files").show(truncate=False)

# ── 8. Cleanup (optional) ─────────────────────────────────────────────────────
# Uncomment to drop the table after testing
# spark.sql(f"DROP TABLE IF EXISTS {CATALOG}.{SCHEMA}.{TABLE}")
# spark.sql(f"DROP NAMESPACE IF EXISTS {CATALOG}.{SCHEMA}")

print("\n✓ Spark IRC demo complete\n")
spark.stop()
