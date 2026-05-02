-- ==============================================================================
-- Northwind Performance Test Database
-- Específicamente diseñada para el Analizador de Rendimiento de Consultas
-- ==============================================================================

-- 1. Creamos la base de datos desde cero
DROP DATABASE IF EXISTS northwind_perf;
CREATE DATABASE northwind_perf;
USE northwind_perf;

-- 2. Estructura de Tablas (Clásico modelo relacional complejo)
CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL,
    description TEXT
);

CREATE TABLE suppliers (
    supplier_id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    contact_name VARCHAR(100),
    country VARCHAR(50)
);

CREATE TABLE products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    supplier_id INT,
    category_id INT,
    unit_price DECIMAL(10, 2) DEFAULT 0,
    units_in_stock INT DEFAULT 0,
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    contact_name VARCHAR(100),
    country VARCHAR(50),
    city VARCHAR(50),
    registration_date DATE
);

CREATE TABLE employees (
    employee_id INT AUTO_INCREMENT PRIMARY KEY,
    last_name VARCHAR(50) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    title VARCHAR(50),
    hire_date DATE
);

CREATE TABLE shippers (
    shipper_id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL
);

CREATE TABLE orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    employee_id INT,
    order_date DATE,
    shipper_id INT,
    freight DECIMAL(10, 2),
    ship_country VARCHAR(50),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (shipper_id) REFERENCES shippers(shipper_id)
);

CREATE TABLE order_details (
    order_id INT,
    product_id INT,
    unit_price DECIMAL(10, 2) NOT NULL,
    quantity INT NOT NULL,
    discount DECIMAL(4, 2) DEFAULT 0,
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 3. Índices (Vitales para probar el analizador de rendimiento)
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_supplier ON products(supplier_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_employee ON orders(employee_id);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_order_details_product ON order_details(product_id);
CREATE INDEX idx_customers_country ON customers(country);

-- 4. Procedimiento Almacenado para generar carga masiva de datos reales
DELIMITER $$

CREATE PROCEDURE SeedNorthwindPerf()
BEGIN
    DECLARE i INT DEFAULT 1;
    DECLARE o INT DEFAULT 1;
    
    -- Insertar Categorías (8)
    INSERT INTO categories (category_name, description) VALUES 
    ('Beverages', 'Soft drinks, coffees, teas, beers, and ales'),
    ('Condiments', 'Sweet and savory sauces, relishes, spreads, and seasonings'),
    ('Confections', 'Desserts, candies, and sweet breads'),
    ('Dairy Products', 'Cheeses'),
    ('Grains/Cereals', 'Breads, crackers, pasta, and cereal'),
    ('Meat/Poultry', 'Prepared meats'),
    ('Produce', 'Dried fruit and bean curd'),
    ('Seafood', 'Seaweed and fish');

    -- Insertar Transportistas (3)
    INSERT INTO shippers (company_name) VALUES 
    ('Speedy Express'), ('United Package'), ('Federal Shipping');

    -- Generar 50 Proveedores
    SET i = 1;
    WHILE i <= 50 DO
        INSERT INTO suppliers (company_name, contact_name, country) 
        VALUES (CONCAT('Supplier ', i), CONCAT('Contact ', i), ELT(MOD(i, 5) + 1, 'USA', 'UK', 'Germany', 'France', 'Japan'));
        SET i = i + 1;
    END WHILE;

    -- Generar 100 Empleados
    SET i = 1;
    WHILE i <= 100 DO
        INSERT INTO employees (first_name, last_name, title, hire_date) 
        VALUES (CONCAT('First', i), CONCAT('Last', i), 'Sales Representative', DATE_ADD('2010-01-01', INTERVAL MOD(i, 3650) DAY));
        SET i = i + 1;
    END WHILE;

    -- Generar 500 Productos
    SET i = 1;
    WHILE i <= 500 DO
        INSERT INTO products (product_name, supplier_id, category_id, unit_price, units_in_stock) 
        VALUES (
            CONCAT('Product ', i), 
            MOD(i, 50) + 1, 
            MOD(i, 8) + 1, 
            RAND() * 100 + 5, 
            FLOOR(RAND() * 500)
        );
        SET i = i + 1;
    END WHILE;

    -- Generar 1000 Clientes
    SET i = 1;
    WHILE i <= 1000 DO
        INSERT INTO customers (company_name, contact_name, country, city, registration_date) 
        VALUES (
            CONCAT('Customer ', i), 
            CONCAT('Contact ', i), 
            ELT(MOD(i, 7) + 1, 'USA', 'UK', 'Germany', 'France', 'Spain', 'Italy', 'Brazil'),
            CONCAT('City ', MOD(i, 50)),
            DATE_ADD('2015-01-01', INTERVAL MOD(i, 2000) DAY)
        );
        SET i = i + 1;
    END WHILE;

    -- Generar 10,000 Órdenes de compra y sus Detalles (Carga Masiva)
    SET o = 1;
    WHILE o <= 10000 DO
        INSERT INTO orders (customer_id, employee_id, order_date, shipper_id, freight, ship_country)
        VALUES (
            MOD(o, 1000) + 1,
            MOD(o, 100) + 1,
            DATE_ADD('2018-01-01', INTERVAL FLOOR(RAND() * 1500) DAY),
            MOD(o, 3) + 1,
            RAND() * 50 + 10,
            ELT(MOD(o, 7) + 1, 'USA', 'UK', 'Germany', 'France', 'Spain', 'Italy', 'Brazil')
        );

        -- Añadir de 1 a 5 Detalles por Orden
        SET i = 1;
        WHILE i <= (MOD(o, 5) + 1) DO
            INSERT IGNORE INTO order_details (order_id, product_id, unit_price, quantity, discount)
            VALUES (
                o,
                MOD(o * i, 500) + 1,
                RAND() * 100 + 5,
                FLOOR(RAND() * 20) + 1,
                IF(RAND() > 0.8, 0.1, 0)
            );
            SET i = i + 1;
        END WHILE;

        SET o = o + 1;
    END WHILE;

END$$
DELIMITER ;

-- 5. Ejecutar el procedimiento para que se llene la base de datos automáticamente
CALL SeedNorthwindPerf();
