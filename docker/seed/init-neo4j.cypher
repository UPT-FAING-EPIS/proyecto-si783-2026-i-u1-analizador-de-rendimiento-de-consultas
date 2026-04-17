// Neo4j Social Commerce Graph Seed Data
// Structure: 500 Users, 100 Products, 10 Categories
// Relationships: FOLLOWS (1000), PURCHASED (1500), VIEWED (2000), LIKES (800)
// Total: ~500 nodes, ~5300 relationships

// ===== CATEGORIES =====
// 10 product categories
CREATE (c1:Category {id: 1, name: 'Electronics', description: 'Electronic devices and accessories'})
CREATE (c2:Category {id: 2, name: 'Fashion', description: 'Clothing and accessories'})
CREATE (c3:Category {id: 3, name: 'Home', description: 'Home and garden products'})
CREATE (c4:Category {id: 4, name: 'Sports', description: 'Sports and outdoor gear'})
CREATE (c5:Category {id: 5, name: 'Books', description: 'Books and educational materials'})
CREATE (c6:Category {id: 6, name: 'Food', description: 'Food and beverages'})
CREATE (c7:Category {id: 7, name: 'Beauty', description: 'Beauty and personal care'})
CREATE (c8:Category {id: 8, name: 'Toys', description: 'Toys and games'})
CREATE (c9:Category {id: 9, name: 'Tools', description: 'Tools and hardware'})
CREATE (c10:Category {id: 10, name: 'Other', description: 'Miscellaneous products'});

// ===== USERS =====
// 500 users distributed across 5 countries
// Pattern: 100 users per country
UNWIND ['US', 'UK', 'DE', 'FR', 'JP'] AS country
UNWIND range(1, 100) AS idx
WITH country, idx, ((idx - 1) * 5 + 1) AS user_id
CREATE (u:User {
  id: user_id,
  name: 'User_' + toString(user_id),
  email: 'user' + toString(user_id) + '@example.com',
  country: country,
  registration_date: date({year: 2023, month: 1, day: 1}) + duration({days: (user_id % 365)})
});

// ===== PRODUCTS =====
// 100 products with prices and stock levels
UNWIND range(1, 100) AS product_id
WITH product_id,
  (product_id % 10) + 1 AS category_id,
  (product_id * 13 % 999) + 10 AS price,
  (product_id * 7 % 500) + 50 AS stock
CREATE (p:Product {
  id: product_id,
  title: 'Product_' + toString(product_id),
  price: price,
  category_id: category_id,
  stock: stock,
  created_date: date({year: 2023, month: 1, day: 1}) + duration({days: (product_id % 365)})
});

// ===== PURCHASED RELATIONSHIPS =====
// 1500 purchases: each user typically buys 3-4 products
MATCH (u:User), (p:Product)
WHERE (u.id * 7 + p.id * 11) % 167 < 3
WITH u, p, (u.id * 13 + p.id * 17) % 5 + 1 AS quantity
CREATE (u)-[:PURCHASED {quantity: quantity, purchase_date: date({year: 2024, month: 1, day: 1})}]->(p);

// ===== VIEWED RELATIONSHIPS =====
// 2000 product views: each user typically views 4 products, each product viewed ~20 times
MATCH (u:User), (p:Product)
WHERE (u.id * 11 + p.id * 13) % 125 < 4
CREATE (u)-[:VIEWED {view_date: date({year: 2024, month: 1, day: 1})}]->(p);

// ===== FOLLOWS RELATIONSHIPS =====
// 1000 social follows: sparse network, ~2 follows per user
MATCH (u1:User), (u2:User)
WHERE u1.id < u2.id
  AND (u1.id * 19 + u2.id * 23) % 500 < 2
CREATE (u1)-[:FOLLOWS {since: date({year: 2023, month: 6, day: 1})}]->(u2);

// ===== LIKES RELATIONSHIPS =====
// 800 product likes: ~1.6 likes per user
MATCH (u:User), (p:Product)
WHERE (u.id * 17 + p.id * 19) % 250 < 1.6
CREATE (u)-[:LIKES]->(p);

// ===== CREATE INDEXES FOR BETTER QUERY PERFORMANCE =====
CREATE INDEX idx_user_country IF NOT EXISTS FOR (u:User) ON (u.country);
CREATE INDEX idx_user_id IF NOT EXISTS FOR (u:User) ON (u.id);
CREATE INDEX idx_product_id IF NOT EXISTS FOR (p:Product) ON (p.id);
CREATE INDEX idx_product_price IF NOT EXISTS FOR (p:Product) ON (p.price);
CREATE INDEX idx_category_id IF NOT EXISTS FOR (c:Category) ON (c.id);

// ===== CREATE CONSTRAINTS =====
CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT product_id_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT category_id_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.id IS UNIQUE;
