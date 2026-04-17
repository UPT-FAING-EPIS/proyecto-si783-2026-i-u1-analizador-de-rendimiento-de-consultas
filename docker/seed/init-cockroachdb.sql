-- ============================================================================
-- Query Analyzer - CockroachDB Distributed Test Data (REGIONAL SHARDING)
-- ============================================================================
-- This script demonstrates CockroachDB's distributed capabilities with
-- data partitioned by region and demonstrates sharding patterns.
--
-- Tables:
--   - regional_users (1000 rows) - Users distributed across 5 regions
--   - regional_transactions (5000 rows) - Transactions with regional affinity
--   - shard_distribution (5 rows) - Meta-info about sharding
--   - hot_keys_log (500 rows) - Hotspot monitoring
--
-- Key Features:
--   - Demonstrates LOCAL SHARD queries (Query 1: single region = fast)
--   - Demonstrates CROSS-SHARD queries (Query 2-4: multiple regions = slower)
--   - Shows distributed GROUP BY, JOIN, and AGGREGATION overhead
-- ============================================================================

-- Drop existing tables if they exist
DROP TABLE IF EXISTS hot_keys_log CASCADE;
DROP TABLE IF EXISTS shard_distribution CASCADE;
DROP TABLE IF EXISTS regional_transactions CASCADE;
DROP TABLE IF EXISTS regional_users CASCADE;

-- ============================================================================
-- Regional Users Table (1000 rows)
-- Distributed: 5 regions × 200 users each
-- ============================================================================
CREATE TABLE regional_users (
    user_id SERIAL PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_regional_users_region ON regional_users(region);
CREATE INDEX idx_regional_users_email ON regional_users(email);

INSERT INTO regional_users (region, name, email)
SELECT
    CASE (i % 5)
        WHEN 0 THEN 'US'
        WHEN 1 THEN 'EU'
        WHEN 2 THEN 'APAC'
        WHEN 3 THEN 'LATAM'
        ELSE 'MENA'
    END as region,
    'User_' || i || '_' || CASE (i % 5)
        WHEN 0 THEN 'USA'
        WHEN 1 THEN 'Europe'
        WHEN 2 THEN 'AsiaPacific'
        WHEN 3 THEN 'LatinAmerica'
        ELSE 'MiddleEastNorthAfrica'
    END,
    'user' || i || '@' || CASE (i % 5)
        WHEN 0 THEN 'us-company.com'
        WHEN 1 THEN 'eu-company.com'
        WHEN 2 THEN 'apac-company.com'
        WHEN 3 THEN 'latam-company.com'
        ELSE 'mena-company.com'
    END
FROM generate_series(1, 1000) AS t(i);

-- ============================================================================
-- Regional Transactions Table (5000 rows)
-- ~5 transactions per user, with regional affinity
-- ============================================================================
CREATE TABLE regional_transactions (
    txn_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES regional_users(user_id),
    region VARCHAR(50) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    status VARCHAR(50),
    txn_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_regional_transactions_region ON regional_transactions(region);
CREATE INDEX idx_regional_transactions_status ON regional_transactions(status);
CREATE INDEX idx_regional_transactions_user_id ON regional_transactions(user_id);

WITH user_list AS (
    SELECT user_id, region, ROW_NUMBER() OVER (PARTITION BY region ORDER BY user_id) as rn
    FROM regional_users
)
INSERT INTO regional_transactions (user_id, region, amount, status)
SELECT
    ru.user_id,
    ru.region,
    ROUND((RANDOM() * 9999.99 + 0.01)::NUMERIC, 2),
    CASE (t.i % 4)
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'completed'
        WHEN 2 THEN 'failed'
        ELSE 'refunded'
    END
FROM generate_series(1, 5000) AS t(i)
CROSS JOIN (SELECT COUNT(*) as user_count FROM regional_users) cnt
JOIN regional_users ru ON ru.user_id = ((t.i % cnt.user_count) + 1);

-- ============================================================================
-- Shard Distribution Table (5 rows)
-- Meta-information about how data is distributed
-- ============================================================================
CREATE TABLE shard_distribution (
    shard_id SERIAL PRIMARY KEY,
    region VARCHAR(50) NOT NULL UNIQUE,
    user_count INTEGER,
    transaction_count INTEGER,
    avg_latency_ms DECIMAL(8, 2)
);

INSERT INTO shard_distribution (region, user_count, transaction_count, avg_latency_ms)
VALUES
    ('US', 200, 1000, 5.2),
    ('EU', 200, 1000, 8.5),
    ('APAC', 200, 1000, 12.3),
    ('LATAM', 200, 1000, 15.7),
    ('MENA', 200, 1000, 18.9);

-- ============================================================================
-- Hot Keys Log Table (500 rows)
-- Simulates hotspot/contention monitoring
-- ============================================================================
CREATE TABLE hot_keys_log (
    log_id SERIAL PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    key_pattern VARCHAR(100),
    access_count INTEGER,
    conflict_rate DECIMAL(5, 2),
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO hot_keys_log (region, key_pattern, access_count, conflict_rate)
SELECT
    CASE (i % 5)
        WHEN 0 THEN 'US'
        WHEN 1 THEN 'EU'
        WHEN 2 THEN 'APAC'
        WHEN 3 THEN 'LATAM'
        ELSE 'MENA'
    END,
    'txn_user_' || (i % 50),
    FLOOR(RANDOM() * 50000 + 100)::INT,
    ROUND(RANDOM() * 100, 2)
FROM generate_series(1, 500) AS t(i);

-- ============================================================================
-- Sample Queries for Testing
-- ============================================================================

-- Query 1: LOCAL SHARD QUERY (Fast - single region)
-- Expected: Score 100/100, ~1-5ms
-- SELECT user_id, name, email FROM regional_users WHERE region = 'US' AND email LIKE '%@us-company.com' LIMIT 10;

-- Query 2: CROSS-SHARD GROUP BY (Slower - all regions)
-- Expected: Score 70-80/100, ~50-150ms
-- SELECT region, COUNT(*) as user_count FROM regional_users GROUP BY region ORDER BY user_count DESC;

-- Query 3: DISTRIBUTED JOIN (Heavier - reshuffling)
-- Expected: Score 60-70/100, ~200-500ms
-- SELECT u.region, u.name, COUNT(t.txn_id) as txn_count
-- FROM regional_users u
-- JOIN regional_transactions t ON u.user_id = t.user_id
-- WHERE t.status = 'completed'
-- GROUP BY u.region, u.name
-- HAVING COUNT(t.txn_id) > 3;

-- Query 4: MULTI-REGION AGGREGATION (Complex - consolidation)
-- Expected: Score 75-85/100, ~150-300ms
-- SELECT region, AVG(amount) as avg_txn_amount, MAX(amount) as max_txn_amount, COUNT(*) as total_txns
-- FROM regional_transactions
-- WHERE txn_timestamp > NOW() - INTERVAL '7 days'
-- GROUP BY region
-- ORDER BY avg_txn_amount DESC;

-- Done!
