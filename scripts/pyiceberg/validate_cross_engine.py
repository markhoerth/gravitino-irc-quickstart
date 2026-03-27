"""
Cross-Engine Validation — Gravitino IRC Quickstart
====================================================
Validates that tables created by each engine are visible to all other engines
via the shared Gravitino IRC catalog. This is the core value-prop of IRC:
write with any engine, read with any engine.

Run:  make validate
Or:   docker exec python-runner python3 /app/pyiceberg/validate_cross_engine.py

Expected flow:
  1. Checks which demo tables exist in the IRC
  2. For each table, reads row count via PyIceberg
  3. Prints a cross-engine visibility matrix
"""

import os
import sys
from pyiceberg.catalog import load_catalog

IRC_URI  = os.environ.get("IRC_URI", "http://gravitino-irc:9001/iceberg")
S3_KEY   = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
S3_SEC   = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin123")

catalog = load_catalog("gravitino_irc", **{
    "type": "rest",
    "uri": IRC_URI,
    "s3.endpoint": "http://minio:9000",
    "s3.access-key-id": S3_KEY,
    "s3.secret-access-key": S3_SEC,
    "s3.path-style-access": "true",
    "s3.region": "us-east-1",
})

EXPECTED = {
    "Spark"     : ("demo_spark",      "sales"),
    "Trino"     : ("demo_trino",      "orders"),
    "PyIceberg" : ("demo_pyiceberg",  "customers"),
}

print("\n" + "="*60)
print("  Cross-Engine IRC Visibility Validation")
print("="*60 + "\n")

all_pass = True
for engine, (ns, tbl) in EXPECTED.items():
    try:
        t     = catalog.load_table((ns, tbl))
        snap  = t.current_snapshot()
        count = t.scan().to_arrow().num_rows if snap else 0
        status = f"✓  {count} rows"
    except Exception as e:
        status = f"✗  NOT FOUND ({e})"
        all_pass = False

    print(f"  {engine:<12}  {ns}.{tbl:<30}  {status}")

print()
if all_pass:
    print("  ✓ All engines share the same IRC catalog — metadata federation working!\n")
else:
    print("  ⚠ Some tables missing. Run the missing engine demos first:\n")
    print("      make spark-demo      → creates demo_spark.sales")
    print("      make trino-demo      → creates demo_trino.orders")
    print("      make pyiceberg-demo  → creates demo_pyiceberg.customers\n")
    sys.exit(1)
