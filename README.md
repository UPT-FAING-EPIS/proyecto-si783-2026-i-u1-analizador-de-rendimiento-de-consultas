[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/EukCIKzm)
[![Open in Codespaces](https://classroom.github.com/assets/launch-codespace-2972f46106e565e64193e422d61a12cf1da4916b45550586e14ef0a7c637dd04.svg)](https://classroom.github.com/open-in-codespaces?assignment_repo_id=24102472)

# Query Analyzer

[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue)](https://www.python.org/)
[![uv](https://img.shields.io/badge/Package%20Manager-uv-orange)](https://github.com/astral-sh/uv)

Analizador de planes de ejecucion y metricas reales para SQL, NoSQL, grafos y
TimeSeries, con interfaces CLI y TUI.

## Que puedes hacer

- Consultar planes de ejecucion y metricas observadas directamente en el motor.
- Trabajar con multiples motores desde una sola herramienta CLI/TUI.
- Revisar estructura del plan, tiempos, filas y uso de recursos sin puntajes arbitrarios.
- Solicitar una interpretacion opcional mediante IA, presentada por separado de los datos reales.

## Motores soportados

### SQL

- PostgreSQL
- MySQL
- SQLite
- CockroachDB
- YugabyteDB

### NoSQL

- MongoDB
- DynamoDB

### TimeSeries y grafos

- InfluxDB
- Neo4j

Para detalles de DynamoDB, revisa `docs/adapters/DYNAMODB.md`.

## Instalacion

La forma recomendada es instalar por package manager (Homebrew, Scoop o Snap). Como alternativa, puedes
instalar con binarios de GitHub Releases o ejecutar desde codigo fuente.

### Opcion A (recomendada): Instalacion por package manager

Cada release `v*` publica automaticamente el paquete `qa` via JReleaser.

#### Homebrew (macOS/Linux)

```bash
brew tap andre-carbajal/tap
brew install qa
qa --help
```

#### Scoop (Windows)

```powershell
scoop bucket add andre https://github.com/andre-carbajal/scoop-bucket.git
scoop install qa
qa --help
```

#### Snap (Linux)

```bash
sudo snap install qa
qa --help
```

### Opcion B: Instalar binario desde GitHub Releases

En cada tag `v*` se publican estos artefactos:

- `qa-linux-amd64.tar.gz`
- `qa-macos-arm64.zip`
- `qa-windows-amd64.zip`

#### Linux (amd64)

```bash
tar -xzf qa-linux-amd64.tar.gz
chmod +x qa
sudo mv qa /usr/local/bin/qa
qa --help
```

#### macOS (arm64)

```bash
unzip qa-macos-arm64.zip
chmod +x qa
sudo mv qa /usr/local/bin/qa
qa --help
```

#### Windows (amd64)

1. Descomprime `qa-windows-amd64.zip`.
2. Ubica `qa.exe` dentro de `qa-<version>/bin/`.
3. Agrega esa carpeta al `PATH` o ejecuta el binario directamente.

PowerShell (ejecucion directa):

```powershell
.\qa-2.1.0\bin\qa.exe --help
```

### Opcion C: Ejecutar desde codigo fuente

Requisitos:

- Python 3.14+
- uv

```bash
git clone https://github.com/UPT-FAING-EPIS/proyecto-si783-2026-i-u2-rendimiento-de-consultas-2.git
cd proyecto-si783-2026-i-u2-rendimiento-de-consultas-2
uv sync
uv run query_analyzer
```

Tambien puedes usar:

```bash
python -m query_analyzer
```

## Canales de distribucion

El pipeline de release publica automaticamente en estos canales:

- Homebrew Tap: `andre-carbajal/tap`
- Scoop Bucket: `andre` (`https://github.com/andre-carbajal/scoop-bucket`)
- Snapcraft: paquete `qa`

## Uso rapido

```bash
qa --help
```

Si lo ejecutas desde fuente:

```bash
uv run query_analyzer --help
```

## API REST

La versión `2.1.0` incluye una API FastAPI para exponer los mismos adaptadores y
reportes factuales usados por la CLI y la TUI.

```bash
uv sync
uv run qa-api
```

El servidor escucha por defecto en `http://127.0.0.1:8000`. Puedes cambiar host
y puerto con `QA_API_HOST` y `QA_API_PORT`; por ejemplo,
`$env:QA_API_PORT="8001"; uv run qa-api`.

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`
- Base de endpoints: `/api/v1/analyzer`

Ejemplo con SQLite:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyzer/explain \
  -H "Content-Type: application/json" \
  -d '{"connection":{"engine":"sqlite","database":":memory:"},"query":"SELECT 1"}'
```

Consulta [docs/API.md](docs/API.md) para los contratos y endpoints disponibles.

## Servidor MCP

Query Analyzer expone una herramienta MCP para agentes de programación. El
servidor usa los perfiles locales de `qa profile` y ejecuta el análisis contra
el core del proyecto, sin requerir que la API FastAPI esté encendida.

```bash
uv sync
uv run python -m query_analyzer.mcp_server
```

Configuración ejemplo para clientes MCP por stdio:

```json
{
  "mcpServers": {
    "query_analyzer": {
      "command": "uv",
      "args": ["run", "python", "-m", "query_analyzer.mcp_server"]
    }
  }
}
```

La tool disponible es `analyze_query(query, profile)`. Si `profile` se omite,
se usa el perfil por defecto configurado en Query Analyzer.

## AI Integration (v2.1.0+)

Query Analyzer now supports **optional AI-powered analysis** via pluggable LLM providers.

### Configure Your LLM Provider

To enable AI insights, set these environment variables:

```bash
# Required: All three must be set
export QA_AI_BASE_URL="https://api.openai.com/v1"     # LLM provider URL
export QA_AI_API_KEY="sk-..."                         # API key
export QA_AI_MODEL="gpt-4o-mini"                      # Model identifier

```

### Supported LLM Providers

| Provider | Base URL | Model Examples | Cost |
|----------|----------|-----------------|------|
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4` | Paid |
| **DeepSeek** | `https://api.deepseek.com/v1` | `deepseek-chat` | Paid (cheap) |
| **Groq** | `https://api.groq.com/openai/v1` | `mixtral-8x7b-32768` | Free |
| **Ollama (Local)** | `http://localhost:11434/v1` | `mistral`, `llama2` | Free (local) |

### Example: Using OpenAI

```bash
export QA_AI_BASE_URL="https://api.openai.com/v1"
export QA_AI_API_KEY="sk-proj-..."
export QA_AI_MODEL="gpt-4o-mini"

qa analyze "SELECT * FROM users" --profile local-postgres
```

Output includes:
- **Plan Summary**: Brief description of execution plan
- **Metrics**: Execution time, rows examined, etc.
- **AI Analysis** (if configured):
  - Summary of query performance
  - Observations (potential issues detected)
  - Recommendations for optimization

### Example: Using Local Ollama

```bash
# Start Ollama with Mistral model
ollama run mistral

# In another terminal
export QA_AI_BASE_URL="http://localhost:11434/v1"
export QA_AI_API_KEY="ollama"
export QA_AI_MODEL="mistral"

qa analyze "SELECT 1" --profile local-sqlite
```

### What Happens If AI Is Not Configured?

The tool gracefully falls back to raw EXPLAIN analysis:
- ✅ Plan tree visualization
- ✅ Execution metrics
- ✅ Performance stats
- ❌ AI-powered recommendations (skipped)

### Programmatic Usage

```python
from query_analyzer.adapters import AdapterRegistry
from query_analyzer.adapters.models import ConnectionConfig
from query_analyzer.core import AIAnalyzer

# Execute EXPLAIN
config = ConnectionConfig(
    engine="postgresql",
    host="localhost",
    database="mydb",
    username="user",
    password="pass"
)
adapter = AdapterRegistry.create("postgresql", config)
with adapter:
    report = adapter.execute_explain("SELECT * FROM users")

# Get AI insights (if configured)
analyzer = AIAnalyzer()
if analyzer.is_configured():
    ai_result = analyzer.analyze(
        plan_json=report.raw_plan or report.plan_summary,
        query=report.query,
        engine=report.engine,
    )
    if ai_result:
        print(f"Summary: {ai_result.summary}")
        print(f"Observations: {ai_result.observations}")
        print(f"Recommendations: {ai_result.recommendations}")
else:
    print("AI not configured")
```

---

## Entorno opcional con Docker

Si quieres levantar servicios de base de datos locales para pruebas:

```bash
cp .env.example .env
make up
make health
```

Servicios incluidos: PostgreSQL, MySQL, MongoDB, Redis, InfluxDB, Neo4j y CockroachDB.

Para apagar:

```bash
make down
```

## Releases

El workflow `.github/workflows/release.yml` se ejecuta automaticamente cuando haces push de un tag `v*`.

- Construye binarios por plataforma con PyInstaller.
- Publica artefactos de release.
- Publica y actualiza package managers via JReleaser.

Comandos de instalacion por canal:

```bash
# Homebrew
brew tap andre-carbajal/tap
brew install qa
```

```bash
# Snap
sudo snap install qa
```

```powershell
# Scoop
scoop bucket add andre https://github.com/andre-carbajal/scoop-bucket.git
scoop install qa
```

## Para desarrolladores

Si quieres contribuir, revisa `CONTRIBUTING.md` para setup, pruebas, estilo de codigo y flujo de PRs.
