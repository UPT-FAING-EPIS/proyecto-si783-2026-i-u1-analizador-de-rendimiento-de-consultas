# API REST

Query Analyzer `2.3.0` expone una API FastAPI sobre los adaptadores existentes.
La API devuelve planes, métricas y datos observados por el motor. No calcula
scores ni clasifica automáticamente la calidad de una consulta.

## Inicio

```bash
uv sync
uv run qa-api
```

Con el binario distribuido tambien puedes usar:

```bash
qa api
```

Direcciones locales:

- API: `http://127.0.0.1:8000/api/v1`
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

El host y puerto se pueden configurar con `QA_API_HOST` y `QA_API_PORT`. Por
compatibilidad local, `QA_API_PORT=8001` conserva la dirección usada en versiones
anteriores.

## Endpoints

| Método | Ruta | Propósito |
|---|---|---|
| `GET` | `/analyzer/engines` | Lista motores registrados |
| `POST` | `/analyzer/explain` | Ejecuta el análisis factual de una consulta |
| `POST` | `/analyzer/metrics` | Obtiene métricas del motor |
| `POST` | `/analyzer/slow-queries` | Consulta operaciones lentas soportadas |
| `POST` | `/analyzer/engine-info` | Obtiene versión e información del motor |
| `POST` | `/analyzer/ai` | Interpreta un plan mediante un proveedor compatible |

Todas las rutas de la tabla usan el prefijo `/api/v1`.

## Conexión

```json
{
  "engine": "postgresql",
  "host": "localhost",
  "port": 5432,
  "username": "postgres",
  "password": "secret",
  "database": "query_analyzer",
  "ssl": false
}
```

`password` y las claves de IA se modelan como secretos. Las respuestas de error
no devuelven excepciones de drivers ni valores de conexión.

## EXPLAIN

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyzer/explain \
  -H "Content-Type: application/json" \
  -d '{"connection":{"engine":"sqlite","database":":memory:"},"query":"SELECT 1"}'
```

La respuesta contiene `plan_tree`, `plan_summary`, `raw_plan`, `metrics`,
`execution_time_ms` y `analyzed_at`.

## IA opcional

El endpoint `/analyzer/ai` recibe la configuración en cada solicitud. La clave
no se persiste.

```json
{
  "plan_json": {"node_type": "Seq Scan"},
  "query": "SELECT * FROM users",
  "engine": "postgresql",
  "ai_config": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "secret",
    "model": "gpt-4o-mini"
  }
}
```

El contenido generado por IA se mantiene separado de las métricas factuales.
Debe considerarse interpretación asistida, no evidencia producida por el motor.
