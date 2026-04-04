-- ============================================================================
-- Query Analyzer - MySQL Test Data
-- ============================================================================
-- This script creates test tables and data for demonstrating query performance
-- patterns: index usage, full table scans, nested loops, etc.
--
-- Tables:
--   - customers (100 rows) - Small table for JOINs
--   - orders (100 rows) - Small table with some indexes
--   - order_items (500 rows) - Medium table for nested loops
--   - large_table (10000 rows) - Large table for full table scans
--   - slow_queries_log (1000 rows) - Sample slow query logs
-- ============================================================================

-- Drop existing tables if they exist
DROP TABLE IF EXISTS slow_queries_log;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS large_table;

-- ============================================================================
-- Customers Table (100 rows)
-- ============================================================================
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    country VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_country ON customers(country);

-- Insert 100 customers
DELIMITER $$
BEGIN NOT ATOMIC
  DECLARE i INT DEFAULT 1;
  WHILE i <= 100 DO
    INSERT INTO customers (name, email, country) VALUES (
      CONCAT('Customer ', i),
      CONCAT('customer', i, '@example.com'),
      CASE MOD(i, 5)
        WHEN 0 THEN 'USA'
        WHEN 1 THEN 'UK'
        WHEN 2 THEN 'Canada'
        WHEN 3 THEN 'Germany'
        ELSE 'France'
      END
    );
    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

-- ============================================================================
-- Orders Table (100 rows) - WITH indexes
-- ============================================================================
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date DATE DEFAULT CURDATE(),
    total_amount DECIMAL(10, 2),
    status VARCHAR(50),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_status ON orders(status);

-- Insert 100 orders
DELIMITER $$
BEGIN NOT ATOMIC
  DECLARE i INT DEFAULT 1;
  WHILE i <= 100 DO
    INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES (
      (MOD(i - 1, 100) + 1),
      DATE_SUB(CURDATE(), INTERVAL MOD(i, 30) DAY),
      ROUND(RAND() * 9990 + 10, 2),
      CASE MOD(i, 4)
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'processing'
        WHEN 2 THEN 'shipped'
        ELSE 'delivered'
      END
    );
    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

-- ============================================================================
-- Order Items Table (500 rows) - For nested loops demonstrations
-- ============================================================================
CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT,
    quantity INT,
    unit_price DECIMAL(10, 2),
    FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
-- Intentionally NO index on product_id to force full table scans

-- Insert 500 order items
DELIMITER $$
BEGIN NOT ATOMIC
  DECLARE i INT DEFAULT 1;
  WHILE i <= 500 DO
    INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (
      MOD(i - 1, 100) + 1,
      FLOOR(RAND() * 1000),
      FLOOR(RAND() * 10 + 1),
      ROUND(RAND() * 99 + 1, 2)
    );
    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

-- ============================================================================
-- Large Table (10,000 rows) - For full table scan demonstrations
-- ============================================================================
CREATE TABLE large_table (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_value VARCHAR(100),
    numeric_value INT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_large_table_category ON large_table(category);

-- Insert 10,000 rows
DELIMITER $$
BEGIN NOT ATOMIC
  DECLARE i INT DEFAULT 1;
  WHILE i <= 10000 DO
    INSERT INTO large_table (data_value, numeric_value, category) VALUES (
      CONCAT('value_', i, '_', MD5(CAST(i AS CHAR))),
      MOD((i * 7 + FLOOR(RAND() * 1000)), 50000),
      CASE MOD(i, 10)
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
    );
    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

-- ============================================================================
-- Slow Queries Log Table (1000 rows) - Sample data for analysis
-- ============================================================================
CREATE TABLE slow_queries_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_text TEXT,
    execution_time_ms INT,
    rows_affected INT,
    query_type VARCHAR(50),
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_slow_queries_log_execution_time ON slow_queries_log(execution_time_ms);

-- Insert 1000 slow query records
DELIMITER $$
BEGIN NOT ATOMIC
  DECLARE i INT DEFAULT 1;
  WHILE i <= 1000 DO
    INSERT INTO slow_queries_log (query_text, execution_time_ms, rows_affected, query_type) VALUES (
      CONCAT('SELECT * FROM large_table WHERE category = ''', CHAR(65 + MOD(i, 10)), ''' AND numeric_value > ', MOD(i, 40000)),
      FLOOR(RAND() * 5000 + 100),
      FLOOR(RAND() * 5000),
      CASE MOD(i, 5)
        WHEN 0 THEN 'SELECT'
        WHEN 1 THEN 'JOIN'
        WHEN 2 THEN 'AGGREGATE'
        WHEN 3 THEN 'UPDATE'
        ELSE 'DELETE'
      END
    );
    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

-- ============================================================================
-- Sample Queries for Testing
-- ============================================================================

-- Query 1: INDEX SCAN (uses idx_customers_email)
-- SELECT * FROM customers WHERE email = 'customer1@example.com';

-- Query 2: FULL TABLE SCAN (no index on numeric_value)
-- SELECT * FROM large_table WHERE numeric_value > 30000;

-- Query 3: NESTED LOOP JOIN (JOIN without proper optimization)
-- SELECT o.id, oi.product_id
-- FROM orders o
-- JOIN order_items oi ON o.id = oi.order_id
-- WHERE o.customer_id = 5;

-- Query 4: AGGREGATE with GROUP BY
-- SELECT category, COUNT(*) FROM large_table GROUP BY category;

-- Query 5: Complex JOIN (multiple tables)
-- SELECT c.name, o.total_amount, oi.product_id, oi.quantity
-- FROM customers c
-- JOIN orders o ON c.id = o.customer_id
-- JOIN order_items oi ON o.id = oi.order_id
-- WHERE o.status = 'delivered'
-- ORDER BY o.order_date DESC;

-- ============================================================================
-- Optimize tables for statistics
-- ============================================================================
ANALYZE TABLE customers;
ANALYZE TABLE orders;
ANALYZE TABLE order_items;
ANALYZE TABLE large_table;
ANALYZE TABLE slow_queries_log;

-- Done!
