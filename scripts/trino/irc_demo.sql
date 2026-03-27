-- ─────────────────────────────────────────────────────────────────────────────
-- Trino IRC Demo — Gravitino Quickstart
-- Run:   make trino-demo
-- Shell: make trino-shell
--
-- Catalog: 'iceberg'  (Trino name, maps to Gravitino IRC via REST)
-- All DDL/DML goes directly to IRC → MySQL metadata + MinIO data files.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Explore ────────────────────────────────────────────────────────────────
SHOW CATALOGS;
SHOW SCHEMAS FROM iceberg;

-- ── 2. Create Schema ──────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS iceberg.demo_trino
WITH (location = 's3://warehouse/demo_trino/');

USE iceberg.demo_trino;

-- ── 3. Create Iceberg Table ───────────────────────────────────────────────────
-- Trino uses the iceberg connector pointing at Gravitino IRC via REST protocol.
-- Tables created here are fully visible to Spark and PyIceberg.
CREATE TABLE IF NOT EXISTS orders (
    order_id     BIGINT,
    customer_id  VARCHAR,
    product_sku  VARCHAR,
    quantity     INTEGER,
    unit_price   DOUBLE,
    status       VARCHAR,
    order_date   DATE
)
WITH (
    format            = 'PARQUET',
    partitioning      = ARRAY['month(order_date)'],
    format_version    = 2
);

-- ── 4. Insert Data ────────────────────────────────────────────────────────────
INSERT INTO iceberg.demo_trino.orders VALUES
  (1001, 'CUST-A', 'SKU-001', 2, 49.99,  'SHIPPED',   DATE '2024-01-10'),
  (1002, 'CUST-B', 'SKU-002', 1, 199.00, 'DELIVERED', DATE '2024-01-15'),
  (1003, 'CUST-A', 'SKU-003', 5, 9.99,   'PENDING',   DATE '2024-02-01'),
  (1004, 'CUST-C', 'SKU-001', 1, 49.99,  'SHIPPED',   DATE '2024-02-20'),
  (1005, 'CUST-D', 'SKU-004', 3, 75.00,  'DELIVERED', DATE '2024-03-05'),
  (1006, 'CUST-B', 'SKU-002', 2, 199.00, 'CANCELLED', DATE '2024-03-18'),
  (1007, 'CUST-E', 'SKU-005', 1, 299.99, 'PENDING',   DATE '2024-04-02');

-- ── 5. Queries ────────────────────────────────────────────────────────────────
-- Basic select
SELECT * FROM iceberg.demo_trino.orders ORDER BY order_date;

-- Revenue by status
SELECT
    status,
    COUNT(*)                              AS order_count,
    ROUND(SUM(quantity * unit_price), 2) AS total_revenue
FROM iceberg.demo_trino.orders
GROUP BY status
ORDER BY total_revenue DESC;

-- Monthly revenue trend
SELECT
    CAST(date_trunc('month', order_date) AS DATE) AS month,
    COUNT(*)                                       AS orders,
    ROUND(SUM(quantity * unit_price), 2)           AS revenue
FROM iceberg.demo_trino.orders
GROUP BY 1
ORDER BY 1;

-- ── 6. Iceberg Metadata Tables ────────────────────────────────────────────────
-- Snapshot history
SELECT snapshot_id, committed_at, operation, summary
FROM iceberg.demo_trino."orders$snapshots"
ORDER BY committed_at;

-- Data files
SELECT file_path, record_count, file_size_in_bytes
FROM iceberg.demo_trino."orders$files";

-- Table history
SELECT * FROM iceberg.demo_trino."orders$history";

-- ── 7. Schema Evolution ───────────────────────────────────────────────────────
ALTER TABLE iceberg.demo_trino.orders ADD COLUMN shipping_address VARCHAR;

-- Update rows (Iceberg v2 row-level delete + re-insert)
UPDATE iceberg.demo_trino.orders
SET status = 'DELIVERED'
WHERE order_id = 1001;

-- Verify
SELECT order_id, status FROM iceberg.demo_trino.orders WHERE order_id = 1001;

-- ── 8. Time Travel ────────────────────────────────────────────────────────────
-- Get a snapshot ID first:
-- SELECT snapshot_id FROM iceberg.demo_trino."orders$snapshots" ORDER BY committed_at LIMIT 1;

-- Then time travel:
-- SELECT * FROM iceberg.demo_trino.orders FOR VERSION AS OF <snapshot_id>;

-- ── 9. Cross-Engine Visibility Check ─────────────────────────────────────────
-- Tables created by Spark (demo_spark.sales) should appear here too.
SHOW TABLES FROM iceberg.demo_spark;
SELECT * FROM iceberg.demo_spark.sales LIMIT 5;

-- ── 10. Optional Cleanup ──────────────────────────────────────────────────────
-- DROP TABLE IF EXISTS iceberg.demo_trino.orders;
-- DROP SCHEMA IF EXISTS iceberg.demo_trino;
