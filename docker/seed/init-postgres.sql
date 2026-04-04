-- ============================================================================
-- Query Analyzer - PostgreSQL Test Data
-- ============================================================================
-- This script creates test tables and data for demonstrating query performance
-- patterns: index scans, sequential scans, nested loops, etc.
--
-- Tables:
--   - customers (100 rows) - Small table for JOINs
--   - orders (100 rows) - Small table with some indexes
--   - order_items (500 rows) - Medium table for nested loops
--   - large_table (10000 rows) - Large table for sequential scans
--   - slow_queries_log (1000 rows) - Sample slow query logs
-- ============================================================================

-- Drop existing tables if they exist
DROP TABLE IF EXISTS slow_queries_log CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS large_table CASCADE;

-- ============================================================================
-- Customers Table (100 rows)
-- ============================================================================
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    country VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_country ON customers(country);

INSERT INTO customers (name, email, country)
SELECT
    'Customer ' || i,
    'customer' || i || '@example.com',
    CASE (i % 5)
        WHEN 0 THEN 'USA'
        WHEN 1 THEN 'UK'
        WHEN 2 THEN 'Canada'
        WHEN 3 THEN 'Germany'
        ELSE 'France'
    END
FROM generate_series(1, 100) AS t(i);

-- ============================================================================
-- Orders Table (100 rows) - WITH indexes
-- ============================================================================
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date DATE DEFAULT CURRENT_DATE,
    total_amount DECIMAL(10, 2),
    status VARCHAR(50)
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_status ON orders(status);

INSERT INTO orders (customer_id, order_date, total_amount, status)
SELECT
    (i % 100) + 1,
    CURRENT_DATE - (i % 30 || ' days')::INTERVAL,
    ROUND((RANDOM() * 9990 + 10)::NUMERIC, 2),
    CASE (i % 4)
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'processing'
        WHEN 2 THEN 'shipped'
        ELSE 'delivered'
    END
FROM generate_series(1, 100) AS t(i);

-- ============================================================================
-- Order Items Table (500 rows) - For nested loops demonstrations
-- ============================================================================
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER,
    quantity INTEGER,
    unit_price DECIMAL(10, 2)
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
-- Intentionally NO index on product_id to force sequential scans

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT
    (i % 100) + 1,
    FLOOR(RANDOM() * 1000)::INT,
    FLOOR(RANDOM() * 10 + 1)::INT,
    ROUND((RANDOM() * 99 + 1)::NUMERIC, 2)
FROM generate_series(1, 500) AS t(i);

-- ============================================================================
-- Large Table (10,000 rows) - For sequential scans
-- ============================================================================
CREATE TABLE large_table (
    id SERIAL PRIMARY KEY,
    data_value VARCHAR(100),
    numeric_value INTEGER,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Intentionally create it WITHOUT many indexes to force seq scans
CREATE INDEX idx_large_table_category ON large_table(category);

INSERT INTO large_table (data_value, numeric_value, category)
SELECT
    'value_' || i || '_' || MD5(i::TEXT),
    (i * 7 + FLOOR(RANDOM() * 1000)::INT) % 50000,
    CASE (i % 10)
        WHEN 0 THEN 'A'
        WHEN 1 THEN 'B'
        WHEN 2 THEN 'C'
        WHEN 3 THEN 'D'
        WHEN 4 THEN 'E'
        WHEN 5 THEN 'F'
        WHEN 6 THEN 'G'
        WHEN 7 THEN 'H'
        WHEN 8 THEN 'I'
        ELSE 'J'
    END
FROM generate_series(1, 10000) AS t(i);

-- ============================================================================
-- Slow Queries Log Table (1000 rows) - Sample data for analysis
-- ============================================================================
CREATE TABLE slow_queries_log (
    id SERIAL PRIMARY KEY,
    query_text TEXT,
    execution_time_ms INTEGER,
    rows_affected INTEGER,
    query_type VARCHAR(50),
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_slow_queries_log_execution_time ON slow_queries_log(execution_time_ms);

INSERT INTO slow_queries_log (query_text, execution_time_ms, rows_affected, query_type)
SELECT
    'SELECT * FROM large_table WHERE category = ''' || CHR(65 + (i % 10)) || ''' AND numeric_value > ' || (i % 40000),
    FLOOR(RANDOM() * 5000 + 100)::INT,
    FLOOR(RANDOM() * 5000)::INT,
    CASE (i % 5)
        WHEN 0 THEN 'SELECT'
        WHEN 1 THEN 'JOIN'
        WHEN 2 THEN 'AGGREGATE'
        WHEN 3 THEN 'UPDATE'
        ELSE 'DELETE'
    END
FROM generate_series(1, 1000) AS t(i);

-- ============================================================================
-- Sample Queries for Testing
-- ============================================================================

-- Query 1: INDEX SCAN (will use idx_customers_email)
-- Expected: Fast, uses index
-- SELECT * FROM customers WHERE email = 'customer1@example.com';

-- Query 2: SEQUENTIAL SCAN (no index on numeric_value)
-- Expected: Slower on large_table, full table scan
-- SELECT * FROM large_table WHERE numeric_value > 30000;

-- Query 3: NESTED LOOP (JOIN without proper indexes)
-- Expected: Can produce nested loops
-- SELECT o.id, oi.product_id
-- FROM orders o
-- JOIN order_items oi ON o.id = oi.order_id
-- WHERE o.customer_id = 5;

-- Query 4: AGGREGATE with GROUP BY
-- Expected: Medium performance, depends on data distribution
-- SELECT category, COUNT(*) FROM large_table GROUP BY category;

-- Query 5: Complex JOIN (multiple tables)
-- Expected: Demonstrates query optimizer decisions
-- SELECT c.name, o.total_amount, oi.product_id, oi.quantity
-- FROM customers c
-- JOIN orders o ON c.id = o.customer_id
-- JOIN order_items oi ON o.id = oi.order_id
-- WHERE o.status = 'delivered'
-- ORDER BY o.order_date DESC;

-- ============================================================================
-- Vacuum and Analyze for statistics
-- ============================================================================
VACUUM ANALYZE;

-- Done!
