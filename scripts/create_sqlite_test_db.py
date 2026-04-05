"""Script to generate test SQLite database."""

import sqlite3
from pathlib import Path


def create_test_database(db_path: str | Path = "tests/fixtures/test_database.db") -> None:
    """Create test SQLite database with sample data.

    Creates tables:
    - customers: 100 rows
    - orders: 100 rows
    - order_items: 500 rows
    - products: 50 rows (referenced by order_items)

    Includes various indexes to demonstrate different EXPLAIN outputs.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            country TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute("CREATE INDEX idx_customers_email ON customers(email)")
    cursor.execute("CREATE INDEX idx_customers_country ON customers(country)")

    cursor.execute(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL,
            category TEXT
        )
    """
    )

    cursor.execute("CREATE INDEX idx_products_category ON products(category)")

    cursor.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date DATE,
            total_amount REAL,
            status TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """
    )

    cursor.execute("CREATE INDEX idx_orders_customer_id ON orders(customer_id)")
    cursor.execute("CREATE INDEX idx_orders_status ON orders(status)")

    cursor.execute(
        """
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """
    )

    cursor.execute("CREATE INDEX idx_order_items_order_id ON order_items(order_id)")

    cursor.execute(
        """
        CREATE TABLE slow_queries_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text TEXT,
            execution_time_ms INTEGER,
            rows_affected INTEGER,
            query_type TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    cursor.execute(
        "CREATE INDEX idx_slow_queries_execution_time ON slow_queries_log(execution_time_ms)"
    )

    for i in range(1, 101):
        country = ["USA", "UK", "Canada", "Germany", "France"][i % 5]
        cursor.execute(
            "INSERT INTO customers (name, email, country) VALUES (?, ?, ?)",
            (f"Customer {i}", f"customer{i}@example.com", country),
        )

    categories = ["Electronics", "Clothing", "Food", "Books", "Toys"]
    for i in range(1, 51):
        category = categories[i % len(categories)]
        price = 10.0 + (i % 100)
        cursor.execute(
            "INSERT INTO products (name, price, category) VALUES (?, ?, ?)",
            (f"Product {i}", price, category),
        )

    order_statuses = ["pending", "processing", "shipped", "delivered"]
    for i in range(1, 101):
        customer_id = (i % 100) + 1
        status = order_statuses[i % len(order_statuses)]
        total = 50.0 + (i % 500)
        cursor.execute(
            "INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES (?, DATE('now', '-' || ? || ' days'), ?, ?)",
            (customer_id, i % 30, total, status),
        )

    for i in range(1, 501):
        order_id = (i % 100) + 1
        product_id = (i % 50) + 1
        quantity = (i % 10) + 1
        unit_price = 10.0 + (i % 100)
        cursor.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            (order_id, product_id, quantity, unit_price),
        )

    query_types = ["SELECT", "JOIN", "AGGREGATE", "UPDATE", "DELETE"]
    for i in range(1, 1001):
        query = (
            f"SELECT * FROM products WHERE category = 'Electronics' AND price > {100 + (i % 500)}"
        )
        execution_time = 100 + (i % 5000)
        query_type = query_types[i % len(query_types)]
        cursor.execute(
            "INSERT INTO slow_queries_log (query_text, execution_time_ms, rows_affected, query_type) VALUES (?, ?, ?, ?)",
            (query, execution_time, i % 1000, query_type),
        )

    conn.commit()
    conn.close()

    print(f"[OK] Test database created at {db_path}")
    print("     - Customers: 100 rows (indexed on email, country)")
    print("     - Products: 50 rows (indexed on category)")
    print("     - Orders: 100 rows (indexed on customer_id, status)")
    print("     - Order Items: 500 rows (indexed on order_id, NO index on product_id)")
    print("     - Slow Queries Log: 1000 rows (indexed on execution_time)")


if __name__ == "__main__":
    create_test_database()
