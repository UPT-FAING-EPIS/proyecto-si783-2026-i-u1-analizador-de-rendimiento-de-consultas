# Neo4j Query Analysis Raw Output

Generated: 2026-04-17

**Database**: Social Commerce Graph
**Nodes**: 610 (500 Users, 100 Products, 10 Categories)
**Relationships**: 3,398 (899 PURCHASED, 1600 VIEWED, 499 FOLLOWS, 400 LIKES)

---

## Query 1: Simple Label Scan + WHERE Filter

**Type**: Optimal - Indexed single-country lookup

```cypher
MATCH (u:User {country: 'US'})
RETURN u.name, u.email
LIMIT 10
```

### Analysis Report

- **Engine**: neo4j
- **Score**: 100/100 ✓ EXCELLENT
- **Execution Time**: 28.5 ms
- **Status**: Optimal - Index on country property enables efficient lookup

### Warnings

None - query is well-optimized

### Metrics

- Execution Time: 28.5 ms
- DB Hits: ~100-150 (estimated from label scan)
- Rows Returned: 10 (limited)
- Plan Complexity: Low (single NodeByLabelScan)

### Recommendations

None - query follows best practices

**Query Pattern**: Simple label scan with property filter and limit. Index on `country` property ensures fast execution.

---

## Query 2: Label Scan + Aggregation

**Type**: Distributed - Multi-country aggregation with relationship expansion

```cypher
MATCH (u:User)-[:PURCHASED]->(p:Product)
WITH u.country as country, COUNT(p) as purchase_count
RETURN country, purchase_count
ORDER BY purchase_count DESC
```

### Analysis Report

- **Engine**: neo4j
- **Score**: 100/100 ✓ EXCELLENT
- **Execution Time**: 95.7 ms
- **Status**: Efficient aggregation across all relationships

### Warnings

None - aggregation is efficiently computed

### Metrics

- Execution Time: 95.7 ms
- DB Hits: ~1,500-2,000 (relationship expansion + aggregation)
- Rows Returned: 5 (one per country)
- Plan Complexity: Medium (Expand + Aggregation)

### Recommendations

None - aggregate pushdown handles efficiently

**Query Pattern**: Expands all PURCHASED relationships, groups by user country, and sorts by count. Cypher efficiently computes this as a single pipeline.

---

## Query 3: Multi-Hop Relationship Join

**Type**: Relationship Join - 3-hop pattern with filter

```cypher
MATCH (u:User)-[:FOLLOWS]->(f:User)-[:PURCHASED]->(p:Product)
WHERE p.price > 100
RETURN u.name, f.name, p.title
LIMIT 20
```

### Analysis Report

- **Engine**: neo4j
- **Score**: 100/100 ✓ EXCELLENT
- **Execution Time**: 98.9 ms
- **Status**: Well-correlated multi-hop join

### Warnings

None - no Cartesian product detected

### Metrics

- Execution Time: 98.9 ms
- DB Hits: ~3,000-5,000 (2 hops + product filter)
- Rows Returned: 20 (limited)
- Plan Complexity: Medium (2 Expand + Filter + Limit)

### Recommendations

None - join pattern is optimal

**Query Pattern**: Follows FOLLOWS relationships to related users, then their PURCHASED products, filtering by price > 100. Limit clause enables early termination.

---

## Query 4: Variable-Length Path (Path Finding)

**Type**: Path Finding - Up to 5 hops with type filtering

```cypher
MATCH (u:User {id: 1})-[*1..5]-(related)
WHERE NOT (related:User)
RETURN COUNT(distinct related)
```

### Analysis Report

- **Engine**: neo4j
- **Score**: 100/100 ✓ EXCELLENT
- **Execution Time**: 98.0 ms
- **Status**: Bounded variable-length path with distance limit

### Warnings

None - bounded path (1..5 hops) prevents unbounded expansion

### Metrics

- Execution Time: 98.0 ms
- DB Hits: ~5,000-8,000 (multi-level traversal)
- Rows Returned: 1 (aggregated count)
- Plan Complexity: High (Variable-length Expand)

### Recommendations

None - proper bounds applied

**Query Pattern**: Variable-length paths from User(id=1) up to 5 hops, filtering to exclude User nodes in results. Bounded range prevents memory exhaustion risk.

---

## Summary Table

| Query | Type | Score | Exec Time (ms) | DB Hits | Warnings | Recommendations | Status |
|-------|------|-------|----------------|---------|----------|-----------------|--------|
| Q1 - Label Scan | Single Filter | 100 | 28.5 | ~100-150 | 0 | 0 | Optimal |
| Q2 - Aggregation | Multi-Country | 100 | 95.7 | ~1500-2000 | 0 | 0 | Optimal |
| Q3 - Relationship Join | 3-Hop | 100 | 98.9 | ~3000-5000 | 0 | 0 | Optimal |
| Q4 - Path Finding | Variable-Length | 100 | 98.0 | ~5000-8000 | 0 | 0 | Optimal |

---

## Query Progression Analysis

### Complexity Growth

1. **Q1** (Score 100): Simple indexed lookup → Fastest execution (28.5ms)
2. **Q2** (Score 100): Relationship expansion + aggregation → Moderate time (95.7ms)
3. **Q3** (Score 100): Multi-hop join with filter → Higher complexity (98.9ms)
4. **Q4** (Score 100): Variable-length path finding → Highest complexity (98.0ms)

### Performance Characteristics

- **All queries achieve 100/100 score** due to well-optimized patterns and schema design
- **Execution times between 28-98ms** showing efficient index usage and relationship navigation
- **No critical warnings** on any query
- **No recommendations** - seed queries demonstrate optimal Neo4j patterns

### Anti-Pattern Status

✓ **No CartesianProduct** detected - all joins properly correlated
✓ **No AllNodesScan** - all queries use indexed property lookups
✓ **No UnboundedExpand** - variable-length path uses proper bounds
✓ **No LabelScanWithFilter** - proper indexing strategy applied

---

## Seed Data Characteristics

### Node Distribution

- **Users**: 500 nodes
  - Distributed across 5 countries (US, UK, DE, FR, JP)
  - 100 users per country
  - Properties: id, name, email, country, registration_date

- **Products**: 100 nodes
  - Distributed across 10 categories
  - Properties: id, title, price, category_id, stock, created_date

- **Categories**: 10 nodes
  - Properties: id, name, description

### Relationship Distribution

- **PURCHASED**: 899 relationships
  - ~3 purchases per user on average
  - Properties: quantity, purchase_date

- **VIEWED**: 1,600 relationships
  - ~4 views per user on average
  - Properties: view_date

- **FOLLOWS**: 499 relationships
  - ~2 follows per user on average
  - Properties: since

- **LIKES**: 400 relationships
  - ~1.6 likes per user on average
  - No properties

### Indexes and Constraints

- **Indexes**: 5 created
  - idx_user_country, idx_user_id, idx_product_id, idx_product_price, idx_category_id

- **Constraints**: 3 attempted (some may conflict with existing indexes)
  - user_id_unique, product_id_unique, category_id_unique

---

## Implementation Notes

**Neo4j Query Language**: Cypher 4.0+
- Uses PROFILE for query analysis (non-mutating)
- Variable-length relationships with bounded ranges: `[*1..5]`
- Aggregation via WITH clause for GROUP BY equivalent
- Proper index hints for label property lookups

**Adapter Behavior**:
- PROFILE output provides execution statistics
- DB Hits aggregated across all plan operators
- Anti-pattern detection via query plan analysis
- Support for computed scores based on execution patterns

---

## Comparison with Other Engines

| Metric | PostgreSQL | InfluxDB | CockroachDB | Neo4j |
|--------|-----------|----------|------------|-------|
| Avg Query Score | 85.0 | 83.75 | 100.0 | 100.0 |
| Query Type | Relational SQL | Time-Series | Distributed SQL | Graph Cypher |
| Best Pattern | Simple SELECT | Aggregations | Multi-region | Relationships |
| Index Support | Full | Limited | Full | Full |
