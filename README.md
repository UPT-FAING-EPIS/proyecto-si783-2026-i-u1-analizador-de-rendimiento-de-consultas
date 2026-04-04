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
│       ├── sql/                 # PostgreSQL, MySQL
│       ├── nosql/               # MongoDB
│       └── timeseries/          # InfluxDB, TimescaleDB
├── tests/                       # Pruebas
│   ├── unit/
│   └── integration/
├── docker/                      # Configuración Docker
│   ├── Dockerfile
│   └── docker-compose.yml
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
cd query-analyzer

# Copiar configuración de entorno
cp .env.example .env

# Levantar servicios (PostgreSQL, MongoDB, InfluxDB + app)
docker-compose -f docker/docker-compose.yml up -d

# Ver logs
docker-compose -f docker/docker-compose.yml logs -f query-analyzer
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

**Variables SQL (PostgreSQL):**
```env
DB_SQL_HOST=localhost
DB_SQL_PORT=5432
DB_SQL_USER=admin
DB_SQL_PASSWORD=password123
DB_SQL_NAME=query_analyzer
```

**Variables NoSQL (MongoDB):**
```env
DB_NOSQL_HOST=localhost
DB_NOSQL_PORT=27017
DB_NOSQL_USER=admin
DB_NOSQL_PASSWORD=password123
DB_NOSQL_NAME=query_analyzer
```

**Variables TimeSeries (InfluxDB):**
```env
DB_TIMESERIES_HOST=localhost
DB_TIMESERIES_PORT=8086
DB_TIMESERIES_USER=admin
DB_TIMESERIES_PASSWORD=password123
DB_TIMESERIES_NAME=query_analyzer
```

## 📚 Dependencias Principales

### Producción
- **textual** - TUI framework moderno
- **rich** - Formatting y colores en terminal
- **psycopg2-binary** - Driver PostgreSQL
- **pydantic** - Validación de datos con tipos
- **pyyaml** - Parseo de YAML
- **typer** - CLI framework

### Desarrollo
- **ruff** - Linter/formatter ultra-rápido
- **mypy** - Type checking estricto
- **pytest** - Framework de testing
- **pre-commit** - Git hooks

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
