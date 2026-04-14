# Query Analyzer 🔍

[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue)](https://www.python.org/)
[![uv](https://img.shields.io/badge/Package%20Manager-uv-orange)](https://github.com/astral-sh/uv)
[![Pre-commit](https://img.shields.io/badge/Pre--commit-enabled-green)](https://pre-commit.com/)
[![Ruff](https://img.shields.io/badge/Code%20Style-Ruff-yellow)](https://github.com/astral-sh/ruff)
[![MyPy](https://img.shields.io/badge/Type%20Checking-MyPy-blue)](https://mypy.readthedocs.io/)

Analizador de rendimiento de consultas para **SQL**, **NoSQL** y **TimeSeries** con interfaz TUI moderna basada en Textual.

## 🚀 Características

- 🎯 Análisis profundo de consultas SQL y NoSQL
- 📊 Soporte para múltiples motores de bases de datos
- 🖥️ Interfaz de terminal moderna (TUI) con Textual
- 🐳 Orquestación con Docker Compose

## 🗄️ Motores de Bases de Datos Soportados

### SQL
- **PostgreSQL** - Con análisis de execution plans
- **MySQL** - Con soporte para EXPLAIN FORMAT=JSON
- **SQLite** - Para testing local
- **CockroachDB** - Base de datos distribuida
- **YugabyteDB** - PostgreSQL compatible distribuido

### NoSQL
- **MongoDB** - Análisis de queries de agregación
- **DynamoDB** - Análisis de queries de clave-valor con 8 anti-patterns detectados

Para documentación detallada sobre DynamoDB, ver [docs/adapters/DYNAMODB.md](docs/adapters/DYNAMODB.md).

### TimeSeries
- **InfluxDB** - Base de datos de series temporales
- **Neo4j** - Base de datos de grafos

## 📋 Requisitos Previos

- **Python 3.14+**
- **uv** (gestor de paquetes moderno)
  - Instalación: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
- **Docker & Docker Compose** (opcional, para servicios de BD)

## 🏗️ Estructura del Proyecto

```
query-analyzer/
├── query_analyzer/              # Código principal
│   ├── __init__.py
│   ├── cli.py                   # Punto de entrada CLI
│   ├── tui/                     # Interfaz de usuario (Textual)
│   ├── core/                    # Motor de análisis
│   │   ├── analyzer.py
│   │   ├── parser.py
│   │   └── recommender.py
│   └── adapters/                # Drivers por motor
│       ├── sql/                 # PostgreSQL, MySQL, SQLite, CockroachDB, YugabyteDB
│       └── nosql/               # MongoDB, Redis
├── tests/                       # Pruebas
│   ├── unit/
│   └── integration/
├── docker/                      # Configuración Docker
│   ├── Dockerfile
│   └── compose.yml
├── docs/                        # Documentación
├── pyproject.toml              # Config de uv
├── uv.lock                     # Bloqueo de dependencias
├── .env.example                # Variables de entorno
├── .gitignore                  # Exclusiones Git
└── README.md                   # Este archivo
```

## 📦 Instalación

### Opción 1: Desarrollo Local

```bash
# Clonar repositorio
git clone https://github.com/UPT-FAING-EPIS/proyecto-si783-2026-i-u1-analizador-de-rendimiento-de-consultas.git
cd proyecto-si783-2026-i-u1-analizador-de-rendimiento-de-consultas

# Sincronizar entorno (instala dependencias automáticamente)
uv sync

# Activar entorno (opcional, uv lo maneja automáticamente)
source .venv/bin/activate  # Linux/Mac
# o
.venv\Scripts\activate  # Windows
```

### Opción 2: Con Docker Compose

```bash
# Copiar configuración de entorno
cp .env.example .env

# Levantar todos los servicios
make up

# Ver logs
make logs

# Detener servicios
make down
```

## 🐳 Entorno Docker

El proyecto incluye un entorno Docker completo con múltiples motores de bases de datos para testing y desarrollo.

### Servicios Disponibles

| Servicio | Puerto | Credenciales por Defecto |
|----------|--------|-------------------------|
| PostgreSQL | 5432 | `postgres` / `postgres123` |
| MySQL | 3306 | `analyst` / `mysql123` |
| MongoDB | 27017 | `admin` / `mongodb123` |
| Redis | 6379 | (sin contraseña) |
| InfluxDB | 8086 | `admin` / `influxdb123` |
| Neo4j | 7687/7474 | `neo4j` / `neo4j123` |
| CockroachDB | 26257/8080 | (sin contraseña) |

### Comandos de Make

```bash
# Iniciar todos los servicios
make up

# Verificar estado de salud de servicios
make health

# Cargar datos de prueba en PostgreSQL y MySQL
make seed

# Ver logs en tiempo real
make logs

# Ver logs de un servicio específico
make logs-postgres
make logs-mysql
make logs-mongodb

# Mostrar contenedores activos
make ps

# Detener servicios (preserva datos)
make down

# Limpiar: elimina contenedores y volúmenes
make reset

# Limpiar imágenes Docker no usadas
make clean

# Ver todos los comandos disponibles
make help
```

### Datos de Prueba

El comando `make seed` popula las bases de datos SQL con tablas de prueba diseñadas para demostrar diferentes patrones de rendimiento:

- **customers** (100 filas) - Tabla pequeña con índices para JOINs
- **orders** (100 filas) - Tabla con índices en customer_id y status
- **order_items** (500 filas) - Para demostrar nested loops (sin índice en product_id)
- **large_table** (10,000 filas) - Para demostrar full table scans
- **slow_queries_log** (1,000 filas) - Registro de queries lentes

Ver `docker/seed/README.md` para detalles completos sobre los datos.

### Ejemplo: Testing Local

```bash
# 1. Levantar todo
make up

# 2. Esperar a que los servicios estén listos
make health

# 3. Cargar datos de prueba
make seed

# 4. Verificar que PostgreSQL está disponible
psql -h localhost -U postgres -d query_analyzer -c "SELECT COUNT(*) FROM customers;"

# 5. Cuando termines
make down
```

## 🛠️ Desarrollo

### Ejecutar la Aplicación

```bash
# Con uv (recomendado)
uv run query_analyzer

# O directamente con Python (después de activar venv)
python -m query_analyzer
```

### Ejecutar Tests

```bash
# Tests unitarios
uv run pytest tests/unit/

# Tests de integración
uv run pytest tests/integration/

# Todos los tests
uv run pytest

# Con cobertura
uv run pytest --cov=query_analyzer
```

### Linting y Formatting

```bash
# Ruff - Linter (fix automático)
uv run ruff check --fix

# Ruff - Formatter
uv run ruff format

# MyPy - Type checking
uv run mypy query_analyzer
```

### Pre-commit Hooks

```bash
# Instalar hooks en el repositorio
uv run pre-commit install

# Ejecutar manualmente en todos los archivos
uv run pre-commit run --all-files

# Los hooks se ejecutarán automáticamente al hacer commit
git commit -m "Mensaje del commit"
```

## 🌍 Variables de Entorno

Copiar `.env.example` a `.env` y ajustar según necesidad:

```bash
cp .env.example .env
```

Ver `.env.example` para la lista completa de variables. Principales:

**Variables PostgreSQL:**
```env
DB_POSTGRES_USER=postgres
DB_POSTGRES_PASSWORD=postgres123
DB_POSTGRES_NAME=query_analyzer
DB_POSTGRES_PORT=5432
```

**Variables MySQL:**
```env
DB_MYSQL_USER=analyst
DB_MYSQL_PASSWORD=mysql123
DB_MYSQL_NAME=query_analyzer
DB_MYSQL_PORT=3306
```

**Variables MongoDB:**
```env
DB_MONGODB_USER=admin
DB_MONGODB_PASSWORD=mongodb123
DB_MONGODB_NAME=query_analyzer
DB_MONGODB_PORT=27017
```

**Variables InfluxDB:**
```env
DB_INFLUXDB_USER=admin
DB_INFLUXDB_PASSWORD=influxdb123
DB_INFLUXDB_NAME=query_analyzer
DB_INFLUXDB_PORT=8086
```

## 📚 Dependencias Principales

### Producción
- **textual** - TUI framework moderno
- **rich** - Formatting y colores en terminal
- **psycopg2-binary** - Driver PostgreSQL
- **mysql-connector-python** - Driver MySQL (cuando se implemente)
- **pymongo** - Driver MongoDB (cuando se implemente)
- **pydantic** - Validación de datos con tipos
- **pyyaml** - Parseo de YAML
- **typer** - CLI framework
- **cryptography** - Cifrado de credenciales

### Desarrollo
- **ruff** - Linter/formatter ultra-rápido
- **mypy** - Type checking estricto
- **pytest** - Framework de testing
- **pre-commit** - Git hooks

### DevOps
- **Docker** - Contenedores
- **Docker Compose** - Orquestación multi-contenedor
- **Make** - Automatización de comandos

## 🔄 Flujo de Desarrollo

1. **Crear rama feature**
   ```bash
   git checkout -b feature/nueva-funcionalidad
   ```

2. **Desarrollar con tipos**
   ```bash
   # MyPy validará los tipos automáticamente al commitear
   ```

3. **Ejecutar tests**
   ```bash
   uv run pytest
   ```

4. **Pre-commit hooks**
   ```bash
   # Los hooks de ruff y mypy se ejecutarán automáticamente
   git add .
   git commit -m "feat: descripción de cambios"
   ```

5. **Push a repositorio**
   ```bash
   git push origin feature/nueva-funcionalidad
   ```

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Asegúrate de que `uv sync` funcione sin errores
2. Ejecuta `uv run pre-commit run --all-files` antes de hacer commit
3. Escribe tests para nuevas funcionalidades
4. Usa type hints en todo el código
