# Guía de Pruebas Manuales

Esta carpeta contiene los recursos necesarios para probar el **Query Performance Analyzer**

## 1. Preparación (Base de Datos)
1. Abre **XAMPP Control Panel** e inicia Apache y MySQL.
2. Ve a [http://localhost/phpmyadmin](http://localhost/phpmyadmin).
3. Crea una base de datos llamada `northwind_perf`.
4. Importa el archivo `northwind_perf.sql` que se encuentra en esta misma carpeta.
   - *Este script creará las tablas y generará automáticamente más de 10,000 registros para que las pruebas sean realistas.*

---
**Nota:** Para ejecutar en windows el analizador desde la consola, debemos estar en la carpeta en donde esta contenido el ejecutable, y usamos el comando:
`qa tui`

## 2. Escenarios de Prueba (Copiar y Pegar)

Abre el Analizador de Consultas y prueba los siguientes casos para validar las advertencias y recomendaciones:

### Escenario 0: Producto Cartesiano (Error Crítico)
**Consulta:**
```sql
SELECT * FROM orders, customers;
```
*   **Qué esperar:** Una advertencia de severidad **CRÍTICA**. El analizador detectará que olvidaste la condición de unión (JOIN), lo cual generaría millones de filas innecesarias.

---

### Escenario 1: Inhibición de índices por funciones
**Consulta:**
```sql
SELECT order_id, customer_id, order_date, freight
FROM orders
WHERE YEAR(order_date) = 2021 AND MONTH(order_date) = 5;
```
*   **Qué esperar:** El analizador advertirá que el uso de `YEAR()` y `MONTH()` impide usar el índice de fecha y recomendará usar un rango de fechas (`>=` y `<`).

---

### Escenario 2: Comodín al inicio (Leading Wildcard)
**Consulta:**
```sql
SELECT product_id, product_name, unit_price
FROM products
WHERE product_name LIKE '%Product%';
```
*   **Qué esperar:** Advertencia sobre el uso de `%` al inicio. Explicará que esto fuerza un "Table Scan" (escaneo total) y sugerirá evitarlo o usar Full-Text Search.

---

### Escenario 3: Subconsulta ineficiente (N+1 oculto)
**Consulta:**
```sql
SELECT customer_id, company_name
FROM customers
WHERE customer_id IN (
    SELECT customer_id
    FROM orders
    WHERE freight > 35.00
);
```
*   **Qué esperar:** Advertencia sobre el uso de `IN` con subconsultas. Recomendará usar `INNER JOIN` o `EXISTS`.

---

### Escenario 4: Uso de OR con múltiples columnas
**Consulta:**
```sql
SELECT order_id, freight, ship_country
FROM orders
WHERE customer_id = 15 OR ship_country = 'USA';
```
*   **Qué esperar:** Advertencia de que el `OR` entre diferentes columnas puede invalidar índices. Sugerirá usar `UNION`.

---

### Escenario 5: Agregación masiva sin filtros
**Consulta:**
```sql
SELECT 
    c.company_name, 
    COUNT(o.order_id) AS total_orders, 
    SUM(o.freight) AS total_freight
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.company_name;
```
*   **Qué esperar:** El analizador detectará que estás procesando toda la tabla sin un `WHERE` o un `LIMIT`. Advertirá sobre el alto consumo de memoria temporal.

