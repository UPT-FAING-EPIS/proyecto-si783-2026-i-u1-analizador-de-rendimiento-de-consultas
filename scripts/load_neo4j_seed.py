#!/usr/bin/env python3
"""Load Neo4j seed data programmatically."""

from datetime import date, timedelta

from neo4j import GraphDatabase


def load_seed_data() -> dict:
    """Load seed data into Neo4j."""
    uri = "bolt://localhost:7687"
    driver = GraphDatabase.driver(uri, auth=("neo4j", "neo4j123"))

    stats = {"created_nodes": 0, "created_relationships": 0}

    with driver.session(database="neo4j") as session:
        # Create categories
        print("Creating categories...")
        for cat_id in range(1, 11):
            categories = [
                ("Electronics", "Electronic devices and accessories"),
                ("Fashion", "Clothing and accessories"),
                ("Home", "Home and garden products"),
                ("Sports", "Sports and outdoor gear"),
                ("Books", "Books and educational materials"),
                ("Food", "Food and beverages"),
                ("Beauty", "Beauty and personal care"),
                ("Toys", "Toys and games"),
                ("Tools", "Tools and hardware"),
                ("Other", "Miscellaneous products"),
            ]
            name, desc = categories[cat_id - 1]
            session.run(
                "CREATE (c:Category {id: $id, name: $name, description: $desc})",
                id=cat_id,
                name=name,
                desc=desc,
            )
        stats["created_nodes"] += 10
        print("  [OK] 10 categories created")

        # Create users
        print("Creating users...")
        countries = ["US", "UK", "DE", "FR", "JP"]
        for country_idx, country in enumerate(countries):
            for idx in range(1, 101):
                user_id = country_idx * 100 + idx
                session.run(
                    "CREATE (u:User {id: $id, name: $name, email: $email, country: $country, registration_date: $reg_date})",
                    id=user_id,
                    name=f"User_{user_id}",
                    email=f"user{user_id}@example.com",
                    country=country,
                    reg_date=date(2023, 1, 1) + timedelta(days=user_id % 365),
                )
        stats["created_nodes"] += 500
        print("  [OK] 500 users created")

        # Create products
        print("Creating products...")
        for product_id in range(1, 101):
            category_id = (product_id % 10) + 1
            price = (product_id * 13 % 999) + 10
            stock = (product_id * 7 % 500) + 50
            session.run(
                "CREATE (p:Product {id: $id, title: $title, price: $price, category_id: $cat_id, stock: $stock, created_date: $created_date})",
                id=product_id,
                title=f"Product_{product_id}",
                price=price,
                cat_id=category_id,
                stock=stock,
                created_date=date(2023, 1, 1) + timedelta(days=product_id % 365),
            )
        stats["created_nodes"] += 100
        print("  [OK] 100 products created")

        # Create PURCHASED relationships
        print("Creating PURCHASED relationships...")
        purchased_count = 0
        for user_id in range(1, 501):
            for product_id in range(1, 101):
                if (user_id * 7 + product_id * 11) % 167 < 3:
                    quantity = (user_id * 13 + product_id * 17) % 5 + 1
                    session.run(
                        "MATCH (u:User {id: $uid}) MATCH (p:Product {id: $pid}) CREATE (u)-[:PURCHASED {quantity: $qty, purchase_date: $pdate}]->(p)",
                        uid=user_id,
                        pid=product_id,
                        qty=quantity,
                        pdate=date(2024, 1, 1),
                    )
                    purchased_count += 1
        stats["created_relationships"] += purchased_count
        print(f"  [OK] {purchased_count} PURCHASED relationships created")

        # Create VIEWED relationships
        print("Creating VIEWED relationships...")
        viewed_count = 0
        for user_id in range(1, 501):
            for product_id in range(1, 101):
                if (user_id * 11 + product_id * 13) % 125 < 4:
                    session.run(
                        "MATCH (u:User {id: $uid}) MATCH (p:Product {id: $pid}) CREATE (u)-[:VIEWED {view_date: $vdate}]->(p)",
                        uid=user_id,
                        pid=product_id,
                        vdate=date(2024, 1, 1),
                    )
                    viewed_count += 1
        stats["created_relationships"] += viewed_count
        print(f"  [OK] {viewed_count} VIEWED relationships created")

        # Create FOLLOWS relationships (INCREASED from 500 < 2 to 200 < 5 for ~2500 follows)
        print("Creating FOLLOWS relationships...")
        follows_count = 0
        for user_id1 in range(1, 501):
            for user_id2 in range(user_id1 + 1, 501):
                if (user_id1 * 19 + user_id2 * 23) % 200 < 5:
                    session.run(
                        "MATCH (u1:User {id: $u1}) MATCH (u2:User {id: $u2}) CREATE (u1)-[:FOLLOWS {since: $since}]->(u2)",
                        u1=user_id1,
                        u2=user_id2,
                        since=date(2023, 6, 1),
                    )
                    follows_count += 1
        stats["created_relationships"] += follows_count
        print(f"  [OK] {follows_count} FOLLOWS relationships created")

        # Create LIKES relationships
        print("Creating LIKES relationships...")
        likes_count = 0
        for user_id in range(1, 501):
            for product_id in range(1, 101):
                if (user_id * 17 + product_id * 19) % 250 < 1.6:
                    session.run(
                        "MATCH (u:User {id: $uid}) MATCH (p:Product {id: $pid}) CREATE (u)-[:LIKES]->(p)",
                        uid=user_id,
                        pid=product_id,
                    )
                    likes_count += 1
        stats["created_relationships"] += likes_count
        print(f"  [OK] {likes_count} LIKES relationships created")

        # Create COMMENTED relationships (NEW - high cardinality for anti-pattern testing)
        print("Creating COMMENTED relationships...")
        commented_count = 0
        for user_id in range(1, 501):
            for product_id in range(1, 101):
                if (user_id * 23 + product_id * 29) % 50 < 5:
                    session.run(
                        "MATCH (u:User {id: $uid}) MATCH (p:Product {id: $pid}) CREATE (u)-[:COMMENTED {comment: 'Nice product!', timestamp: datetime()}]->(p)",
                        uid=user_id,
                        pid=product_id,
                    )
                    commented_count += 1
        stats["created_relationships"] += commented_count
        print(f"  [OK] {commented_count} COMMENTED relationships created")

        # Create indexes
        print("Creating indexes...")
        session.run("CREATE INDEX idx_user_country IF NOT EXISTS FOR (u:User) ON (u.country)")
        session.run("CREATE INDEX idx_product_price IF NOT EXISTS FOR (p:Product) ON (p.price)")
        print("  [OK] 2 indexes created")

        # Create constraints
        print("Creating constraints...")
        try:
            session.run(
                "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE"
            )
        except Exception:
            pass
        try:
            session.run(
                "CREATE CONSTRAINT product_id_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE"
            )
        except Exception:
            pass
        try:
            session.run(
                "CREATE CONSTRAINT category_id_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.id IS UNIQUE"
            )
        except Exception:
            pass
        print("  [OK] 3 constraints attempted")

    driver.close()
    return stats


if __name__ == "__main__":
    print("Loading Neo4j seed data...\n")
    stats = load_seed_data()
    print("\n[OK] Seed data loaded successfully")
    print(f"  Nodes: {stats['created_nodes']}")
    print(f"  Relationships: {stats['created_relationships']}")
