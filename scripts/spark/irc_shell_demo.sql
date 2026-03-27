-- ─────────────────────────────────────────────────────────────────────────────
-- Spark SQL Shell — Gravitino IRC Quick Reference
-- Start:  make spark-sql
-- ─────────────────────────────────────────────────────────────────────────────

-- The default catalog is 'gravitino_irc' (set in spark-defaults.conf).
-- You can reference objects as: gravitino_irc.<schema>.<table>

-- 1. List namespaces (schemas)
SHOW NAMESPACES IN gravitino_irc;

-- 2. Create a namespace
CREATE NAMESPACE IF NOT EXISTS gravitino_irc.sandbox;
USE gravitino_irc.sandbox;

-- 3. Create an Iceberg table
CREATE TABLE IF NOT EXISTS events (
    event_id   BIGINT,
    user_id    STRING,
    event_type STRING,
    payload    STRING,
    ts         TIMESTAMP
)
USING iceberg
PARTITIONED BY (days(ts))
TBLPROPERTIES ('format-version' = '2');

-- 4. Insert data
INSERT INTO events VALUES
  (1, 'u001', 'click',    '{"button":"buy"}',   TIMESTAMP '2024-06-01 10:00:00'),
  (2, 'u002', 'pageview', '{"page":"/home"}',    TIMESTAMP '2024-06-01 10:05:00'),
  (3, 'u001', 'purchase', '{"item":"SKU-999"}',  TIMESTAMP '2024-06-02 14:30:00');

-- 5. Query
SELECT * FROM events ORDER BY ts;

-- 6. Time travel — read at a specific snapshot
-- First get snapshot IDs:
SELECT snapshot_id, committed_at FROM gravitino_irc.sandbox.events.snapshots;
-- Then time-travel:
-- SELECT * FROM gravitino_irc.sandbox.events VERSION AS OF <snapshot_id>;

-- 7. Schema evolution
ALTER TABLE events ADD COLUMN session_id STRING;

-- 8. Inspect metadata
SELECT * FROM gravitino_irc.sandbox.events.history;
SELECT * FROM gravitino_irc.sandbox.events.files;
SELECT * FROM gravitino_irc.sandbox.events.partitions;

-- 9. MERGE (Iceberg v2, upsert)
CREATE TABLE IF NOT EXISTS events_updates (
    event_id   BIGINT,
    user_id    STRING,
    event_type STRING,
    payload    STRING,
    ts         TIMESTAMP,
    session_id STRING
) USING iceberg;

MERGE INTO events t
USING events_updates s ON t.event_id = s.event_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
