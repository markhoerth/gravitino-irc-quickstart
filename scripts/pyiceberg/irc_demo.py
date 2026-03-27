"""
PyIceberg IRC Demo — Gravitino Quickstart
==========================================
Demonstrates creating and populating Iceberg tables in Gravitino IRC
using the PyIceberg library with the REST catalog.

This is the primary test that Gravitino's IRC is correctly implementing
the Iceberg REST spec — PyIceberg is the most spec-faithful client.

Run:  make pyiceberg-demo
Or:   docker exec python-runner python3 /app/pyiceberg/irc_demo.py

Environment vars expected (set by docker-compose):
  AWS_ACCESS_KEY_ID     — MinIO access key
  AWS_SECRET_ACCESS_KEY — MinIO secret key
  IRC_URI               — e.g. http://gravitino-irc:9001/iceberg
"""

import os
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField, StringType, LongType, DoubleType,
    TimestamptzType, IntegerType, BooleanType
)
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import MonthTransform, IdentityTransform
from pyiceberg.table.sorting import SortOrder, SortField
from pyiceberg.expressions import GreaterThanOrEqual, And, LessThan
from datetime import datetime, timezone

# ─── Configuration ────────────────────────────────────────────────────────────
IRC_URI   = os.environ.get("IRC_URI", "http://gravitino-irc:9001/iceberg")
S3_ENDPOINT = "http://minio:9000"
CATALOG_NAME = "gravitino_irc"
NAMESPACE = "demo_pyiceberg"

print("\n" + "="*60)
print("  Gravitino IRC — PyIceberg Demo")
print("="*60)
print(f"  IRC endpoint : {IRC_URI}")
print(f"  S3 endpoint  : {S3_ENDPOINT}\n")

# ─── 1. Connect to Gravitino IRC via REST catalog ─────────────────────────────
print("[1] Connecting to Gravitino IRC REST catalog ...")
catalog = load_catalog(
    CATALOG_NAME,
    **{
        "type": "rest",
        "uri": IRC_URI,
        # S3FileIO configuration for MinIO
        "s3.endpoint": S3_ENDPOINT,
        "s3.access-key-id": os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
        "s3.secret-access-key": os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin123"),
        "s3.path-style-access": "true",
        "s3.region": "us-east-1",
    }
)
print(f"  ✓ Connected — catalog type: {type(catalog).__name__}")

# ─── 2. Create Namespace ──────────────────────────────────────────────────────
print(f"\n[2] Creating namespace '{NAMESPACE}' ...")
try:
    catalog.create_namespace(NAMESPACE)
    print(f"  ✓ Namespace created")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"  ✓ Namespace already exists")
    else:
        raise

print("  Namespaces available:")
for ns in catalog.list_namespaces():
    print(f"    • {'.'.join(ns)}")

# ─── 3. Define Schema ─────────────────────────────────────────────────────────
print("\n[3] Defining Iceberg schema ...")

customer_schema = Schema(
    NestedField(1,  "customer_id",   StringType(),    required=False),
    NestedField(2,  "name",          StringType(),    required=False),
    NestedField(3,  "email",         StringType(),    required=False),
    NestedField(4,  "country",       StringType(),    required=False),
    NestedField(5,  "tier",          StringType(),    required=False),   # BRONZE/SILVER/GOLD
    NestedField(6,  "total_orders",  IntegerType(),   required=False),
    NestedField(7,  "lifetime_value",DoubleType(),    required=False),
    NestedField(8,  "active",        BooleanType(),   required=False),
    NestedField(9,  "created_at",    TimestamptzType(), required=False),
    NestedField(10, "updated_at",    TimestamptzType(), required=False),
)

# Partition by country (identity) and month of created_at
partition_spec = PartitionSpec(
    PartitionField(source_id=4,  field_id=1000, transform=IdentityTransform(), name="country"),
    PartitionField(source_id=9,  field_id=1001, transform=MonthTransform(),    name="created_at_month"),
)

sort_order = SortOrder(
    SortField(source_id=1, transform=IdentityTransform())  # sort by customer_id within each partition
)

# ─── 4. Create Table ──────────────────────────────────────────────────────────
table_id = (NAMESPACE, "customers")
print(f"\n[4] Creating table {NAMESPACE}.customers ...")
try:
    catalog.drop_table(table_id)
    print(f"  ✓ Dropped existing table")
except Exception:
    pass # table doesn't exist yet, that's fine

table = catalog.create_table(
    identifier=table_id,
    schema=customer_schema,
    partition_spec=partition_spec,
    sort_order=sort_order,
    properties={
        "write.format.default":            "parquet",
        "write.parquet.compression-codec": "zstd",
        "format-version":                  "2",
        "write.metadata.delete-after-commit.enabled": "true",
        "write.metadata.previous-versions-max": "5",
    },
)
print(f"  ✓ Table created")

# ─── 5. Write Data via PyArrow ────────────────────────────────────────────────
print("\n[5] Writing data using PyArrow + PyIceberg ...")

now = datetime.now(timezone.utc)

# Build a PyArrow table matching the Iceberg schema

arrow_table = pa.table({
    "customer_id":    pa.array(["C001", "C002", "C003", "C004", "C005", "C006"], type=pa.string()),
    "name":           pa.array(["Alice Smith", "Bob Jones", "Carol White", "Dave Brown", "Eve Davis", "Frank Lee"], type=pa.string()),
    "email":          pa.array(["alice@ex.com", "bob@ex.com", "carol@ex.com", "dave@ex.com", "eve@ex.com", "frank@ex.com"], type=pa.string()),
    "country":        pa.array(["US", "UK", "US", "CA", "UK", "US"], type=pa.string()),
    "tier":           pa.array(["GOLD", "SILVER", "BRONZE", "GOLD", "SILVER", "BRONZE"], type=pa.string()),
    "total_orders":   pa.array([42, 17, 3, 88, 25, 7], type=pa.int32()),
    "lifetime_value": pa.array([12500.0, 3200.0, 450.0, 28000.0, 6100.0, 890.0], type=pa.float64()),
    "active":         pa.array([True, True, False, True, True, True], type=pa.bool_()),
    "created_at":     pa.array([now]*6, type=pa.timestamp("us", tz="UTC")),
    "updated_at":     pa.array([now]*6, type=pa.timestamp("us", tz="UTC")),
})

table.append(arrow_table)
print(f"  ✓ Wrote {len(arrow_table)} rows")

# ─── 6. Read Data Back ───────────────────────────────────────────────────────
print("\n[6] Reading data back from IRC ...")
scan = table.scan()
result = scan.to_arrow()
print(f"  ✓ Read {len(result)} rows")
print(f"\n  Columns: {result.column_names}")

import pandas as pd
df = result.to_pandas()
print("\n  All rows:")
print(df[["customer_id", "name", "country", "tier", "lifetime_value", "active"]].to_string(index=False))

# ─── 7. Filtered Scan (predicate pushdown) ────────────────────────────────────
print("\n[7] Predicate pushdown — US customers only ...")
from pyiceberg.expressions import EqualTo
us_scan = table.scan(row_filter=EqualTo("country", "US"))
us_df = us_scan.to_arrow().to_pandas()
print(f"  ✓ {len(us_df)} US customers found")
print(us_df[["customer_id", "name", "tier", "lifetime_value"]].to_string(index=False))

# ─── 8. Schema Evolution ──────────────────────────────────────────────────────
print("\n[8] Schema evolution — adding 'referral_code' column ...")
with table.update_schema() as update:
    update.add_column("referral_code", StringType(), "Referral tracking code")
print(f"  ✓ Column added. New schema has {len(table.schema().fields)} fields")

# ─── 9. Append Another Batch ─────────────────────────────────────────────────
print("\n[9] Appending second batch (with new column populated) ...")
arrow_batch2 = pa.table({
    "customer_id":    pa.array(["C007", "C008"], type=pa.string()),
    "name":           pa.array(["Grace Kim", "Hank Wu"], type=pa.string()),
    "email":          pa.array(["grace@ex.com", "hank@ex.com"], type=pa.string()),
    "country":        pa.array(["CA", "US"], type=pa.string()),
    "tier":           pa.array(["GOLD", "GOLD"], type=pa.string()),
    "total_orders":   pa.array([55, 102], type=pa.int32()),
    "lifetime_value": pa.array([15000.0, 42000.0], type=pa.float64()),
    "active":         pa.array([True, True], type=pa.bool_()),
    "created_at":     pa.array([now, now], type=pa.timestamp("us", tz="UTC")),
    "updated_at":     pa.array([now, now], type=pa.timestamp("us", tz="UTC")),
    "referral_code":  pa.array(["REF-100", "REF-200"], type=pa.string()),
})
table.append(arrow_batch2)
print(f"  ✓ Appended {len(arrow_batch2)} more rows (total should be 8)")

# ─── 10. Snapshot / Time Travel Info ─────────────────────────────────────────
print("\n[10] Snapshot history ...")
for snap in table.snapshots():
    print(f"  Snapshot {snap.snapshot_id} | op={snap.summary.get('operation')} | ts={snap.timestamp_ms}")

# ─── 11. Table Metadata ───────────────────────────────────────────────────────
print(f"\n[11] Table metadata ...")
print(f"  Location     : {table.location()}")
print(f"  Format ver   : {table.format_version}")
print(f"  Current snap : {table.current_snapshot().snapshot_id if table.current_snapshot() else 'none'}")
print(f"  Partitions   : {table.spec()}")

# ─── 12. List Tables in Namespace ────────────────────────────────────────────
print(f"\n[12] Tables in namespace '{NAMESPACE}':")
for tbl in catalog.list_tables(NAMESPACE):
    print(f"  • {'.'.join(tbl)}")

print("\n✓ PyIceberg IRC demo complete\n")
