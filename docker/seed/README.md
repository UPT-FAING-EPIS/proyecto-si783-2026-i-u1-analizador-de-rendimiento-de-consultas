# Docker Seed Data Documentation

Este directorio contiene scripts para poblar las bases de datos de prueba con datos diseñados para demostrar diferentes patrones de rendimiento de consultas.

## Archivos

### `init-postgres.sql`
Script SQL para PostgreSQL que crea las siguientes tablas:

#### `customers` (100 filas)
Tabla pequeña de clientes con información básica.
- **Índices:** `email`, `country`
- **Uso:** Base para JOINs con otras tablas
- **Patrón:** Tabla pequeña optimizada, buenos índices

```sql
SELECT * FROM customers WHERE email = 'customer1@example.com';  -- INDEX SCAN
```

#### `orders` (100 filas)
Tabla de órdenes con referencias a clientes.
- **Índices:** `customer_id`, `order_date`, `status`
- **Uso:** Tabla mediuma con múltiples índices
- **Patrón:** Índices bien colocados para queries típicas

```sql
SELECT * FROM orders WHERE customer_id = 5 AND status = 'delivered';  -- INDEX SCAN
```

#### `order_items` (500 filas)
Items dentro de órdenes, para demostrar nested loops.
- **Índices:** `order_id` solamente
- **NO hay índice:** `product_id` (fuerza full table scans)
- **Uso:** Demostrar nested loops y falta de índices

```sql
-- NESTED LOOP JOIN (puede ser ineficiente sin índice en product_id)
SELECT o.id, oi.product_id 
FROM orders o 
JOIN order_items oi ON o.id = oi.order_id 
WHERE o.customer_id = 5;
```

#### `large_table` (10,000 filas)
Tabla grande para demostrar sequential scans.
- **Índices:** `category` solamente
- **Uso:** Demostrar full table scans en queries sin índices
- **Patrón:** Mucha data, pocos índices

```sql
-- SEQUENTIAL SCAN (no hay índice en numeric_value)
SELECT * FROM large_table WHERE numeric_value > 30000;  -- SLOW

-- INDEX SCAN (usa índice en category)
SELECT * FROM large_table WHERE category = 'A';  -- FAST
```

#### `slow_queries_log` (1,000 filas)
Registro de ejemplo de queries lentas para análisis.
- **Índices:** `execution_time_ms`
- **Uso:** Datos de ejemplo para logging y auditoría
- **Campos:** query_text, execution_time_ms, rows_affected, query_type

### `init-mysql.sql`
Mismo esquema que PostgreSQL pero con sintaxis MySQL:
- Usa `AUTO_INCREMENT` en lugar de `SERIAL`
- Usa `CURDATE()` en lugar de `CURRENT_DATE`
- Usa `RAND()` en lugar de `RANDOM()`
- Usa `DATETIME` en lugar de `TIMESTAMP`

Todas las tablas, índices y datos son idénticos en concepto.

### `init-mongodb.json`
Datos de ejemplo para MongoDB (formato JSON).

#### Colección `orders`
Estructura desnormalizada con clientes y sus órdenes embebidas:

```json
{
  "_id": 1,
  "customer_name": "Customer 1",
  "email": "customer1@example.com",
  "country": "USA",
  "orders": [
    {
      "order_id": 1,
      "order_date": "2024-01-15",
      "items": [
        {"product_id": 101, "quantity": 2, "price": 29.99}
      ],
      "total_amount": 109.97,
      "status": "delivered"
    }
  ]
}
```

**Características:**
- 10 documentos de clientes
- Cada cliente tiene 1-2 órdenes embebidas
- Cada orden tiene 1-2 items
- Datos realistas con precios y cantidades variadas

## Cómo Usar

### Cargar automáticamente con Make
```bash
make seed
```

Este comando:
1. Conecta a PostgreSQL y ejecuta `init-postgres.sql`
2. Conecta a MySQL y ejecuta `init-mysql.sql`
3. Carga `init-mongodb.json` en MongoDB

### Cargar manualmente - PostgreSQL
```bash
psql -h localhost -U postgres -d query_analyzer -f docker/seed/init-postgres.sql
```

### Cargar manualmente - MySQL
```bash
mysql -h localhost -u analyst -p query_analyzer < docker/seed/init-mysql.sql
```

### Cargar manualmente - MongoDB
```bash
mongoimport --authenticationDatabase admin -u admin -p mongodb123 \
  --db query_analyzer --collection orders \
  --type json --file docker/seed/init-mongodb.json \
  --host localhost --port 27017
```

## Ejemplos de Queries para Testing

### PostgreSQL / MySQL

**Query 1: INDEX SCAN (rápido)**
```sql
EXPLAIN ANALYZE
SELECT * FROM customers WHERE email = 'customer1@example.com';
```
Expected: Index Scan, muy rápido, ~1ms

**Query 2: SEQUENTIAL SCAN (lento)**
```sql
EXPLAIN ANALYZE
SELECT * FROM large_table WHERE numeric_value > 30000;
```
Expected: Seq Scan, más lento, depende del volumen

**Query 3: INDEX USAGE (optimizado)**
```sql
EXPLAIN ANALYZE
SELECT COUNT(*) FROM large_table WHERE category = 'A';
```
Expected: Index Scan, rápido, ~5ms

**Query 4: NESTED LOOPS**
```sql
EXPLAIN ANALYZE
SELECT o.id, oi.product_id, oi.quantity
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
WHERE o.customer_id = 5;
```
Expected: Nested Loop Join o Hash Join, depende del optimizer

**Query 5: COMPLEX JOIN**
```sql
EXPLAIN ANALYZE
SELECT c.name, o.total_amount, COUNT(oi.id) as item_count
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN order_items oi ON o.id = oi.order_id
WHERE o.status IS NOT NULL
GROUP BY c.id, c.name, o.total_amount
ORDER BY o.total_amount DESC;
```
Expected: Multiple joins, puede demostrar índices faltantes

### MongoDB

**Query 1: Find simple**
```javascript
db.orders.find({ country: "USA" })
```

**Query 2: Aggregation pipeline**
```javascript
db.orders.aggregate([
  { $match: { country: "USA" } },
  { $unwind: "$orders" },
  { $group: { 
    _id: "$_id", 
    customer_name: { $first: "$customer_name" },
    total_spent: { $sum: "$orders.total_amount" } 
  }},
  { $sort: { total_spent: -1 } }
])
```

**Query 3: Indexing test**
```javascript
db.orders.createIndex({ "country": 1 })
db.orders.find({ country: "USA" }).explain("executionStats")
```

## Volúmenes de Data

| Tabla | Filas | Propósito |
|-------|-------|----------|
| customers | 100 | Pequeña, para JOINs |
| orders | 100 | Pequeña a mediana |
| order_items | 500 | Mediana, para loops |
| large_table | 10,000 | Grande, para seq scans |
| slow_queries_log | 1,000 | Logging/auditoría |

**Total:** ~11,700 filas en SQL, 10 documentos en MongoDB

## Patrones Demostrables

✅ **Index Scans** - Queries con WHERE en columnas indexadas
✅ **Sequential Scans** - Queries sin índices útiles
✅ **Nested Loops** - JOINs sin suficientes índices
✅ **Hash Joins** - JOINs optimizados
✅ **Aggregate Functions** - GROUP BY, COUNT, SUM
✅ **Sorting** - ORDER BY con/sin índices
✅ **Filtering** - WHERE complejos
✅ **Data Volume** - Tabla de 10K filas para comparar performance

## Nota sobre Volúmenes Persistentes

Por defecto, el `docker-compose.yml` está configurado **SIN volúmenes persistentes** (`docker down -v` elimina datos). Esto es intencional para:
- Ambiente de testing limpio
- Evitar conflictos de datos entre ejecuciones
- Facilitar reproducibilidad

Para persistencia, editar `docker-compose.yml` y agregar volúmenes con nombre.

## Troubleshooting

**"Command 'psql' not found"**
- Instalar PostgreSQL client: `brew install postgresql` (macOS) o `apt install postgresql-client` (Linux)

**"MySQL Access Denied"**
- Verificar contraseña en `.env.example` y `docker-compose.yml`
- Asegurar que MySQL está en estado `healthy`: `make health`

**"MongoDB connection refused"**
- MongoDB tarda en arrancar, esperar 10-15 segundos
- Verificar: `docker logs query-analyzer-mongodb`

**"Tables already exist"**
- DROP TABLE los scripts manejan automáticamente
- O ejecutar: `make reset` y luego `make seed`
