
DROP TABLE IF EXISTS slow_queries_log;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS large_table;

CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    country VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_country ON customers(country);

DELIMITER $$
CREATE PROCEDURE InsertCustomers()
BEGIN
  DECLARE i INT DEFAULT 1;
  START TRANSACTION;
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
  COMMIT;
END$$
DELIMITER ;
CALL InsertCustomers();
DROP PROCEDURE InsertCustomers;


CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date DATE,
    total_amount DECIMAL(10, 2),
    status VARCHAR(50),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_status ON orders(status);

DELIMITER $$
CREATE PROCEDURE InsertOrders()
BEGIN
  DECLARE i INT DEFAULT 1;
  START TRANSACTION;
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
  COMMIT;
END$$
DELIMITER ;
CALL InsertOrders();
DROP PROCEDURE InsertOrders;


CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT,
    quantity INT,
    unit_price DECIMAL(10, 2),
    FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_order_items_order_id ON order_items(order_id);


DELIMITER $$
CREATE PROCEDURE InsertOrderItems()
BEGIN
  DECLARE i INT DEFAULT 1;
  START TRANSACTION;
  WHILE i <= 500 DO
    INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (
      MOD(i - 1, 100) + 1,
      FLOOR(RAND() * 1000),
      FLOOR(RAND() * 10 + 1),
      ROUND(RAND() * 99 + 1, 2)
    );
    SET i = i + 1;
  END WHILE;
  COMMIT;
END$$
DELIMITER ;
CALL InsertOrderItems();
DROP PROCEDURE InsertOrderItems;


CREATE TABLE large_table (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_value VARCHAR(100),
    numeric_value INT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_large_table_category ON large_table(category);


DELIMITER $$
CREATE PROCEDURE InsertLargeTable()
BEGIN
  DECLARE i INT DEFAULT 1;
  START TRANSACTION;
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
  COMMIT;
END$$
DELIMITER ;
CALL InsertLargeTable();
DROP PROCEDURE InsertLargeTable;


CREATE TABLE slow_queries_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    query_text TEXT,
    execution_time_ms INT,
    rows_affected INT,
    query_type VARCHAR(50),
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_slow_queries_log_execution_time ON slow_queries_log(execution_time_ms);


DELIMITER $$
CREATE PROCEDURE InsertSlowQueries()
BEGIN
  DECLARE i INT DEFAULT 1;
  START TRANSACTION;
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
  COMMIT;
END$$
DELIMITER ;
CALL InsertSlowQueries();
DROP PROCEDURE InsertSlowQueries;

ANALYZE TABLE customers;
ANALYZE TABLE orders;
ANALYZE TABLE order_items;
ANALYZE TABLE large_table;
ANALYZE TABLE slow_queries_log;


