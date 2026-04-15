"""Modelos de datos para adapters de bases de datos."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class ConnectionConfig(BaseModel):
    """Configuración de conexión a una base de datos.

    Attributes:
        engine: Motor de base de datos (postgresql, mysql, sqlite, mongodb, etc.)
        host: Dirección del servidor (optional for SQLite)
        port: Puerto de conexión (optional for SQLite)
        database: Nombre o ruta de la base de datos
        username: Usuario para autenticación (optional for SQLite)
        password: Contraseña para autenticación. Puede ser vacío para:
                 - CockroachDB (root sin contraseña en docker)
                 - SQLite (file-based, no auth)
                 Otros engines requieren password no-vacío si se proporciona.
        extra: Parámetros adicionales específicos del motor
    """

    engine: str
    host: str | None = None
    port: int | None = None
    database: str
    username: str | None = None
    password: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("engine", mode="before")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Validate and normalize engine name to lowercase.

        Args:
            v: Engine name

        Returns:
            Lowercase engine name

        Raises:
            ValueError: If engine is not supported
        """
        if not v or not v.strip():
            raise ValueError("engine no puede estar vacío")

        engine_lower = v.strip().lower()
        valid_engines = {
            "postgresql",
            "mysql",
            "sqlite",
            "mongodb",
            "redis",
            "neo4j",
            "cockroachdb",
            "yugabytedb",
            "influxdb",
            "dynamodb",
            "cassandra",
            "elasticsearch",
        }

        if engine_lower not in valid_engines:
            raise ValueError("Motor no soportado")

        return engine_lower

    @field_validator("host", mode="before")
    @classmethod
    def strip_host(cls, v: str | None) -> str | None:
        """Strip whitespace from host."""
        if v is None:
            return None

        stripped = v.strip()
        if not stripped:
            raise ValueError("host no puede estar vacío")

        return stripped

    @field_validator("database", mode="before")
    @classmethod
    def strip_and_validate_database(cls, v: str) -> str:
        """Strip whitespace and validate database name.

        Args:
            v: Database name

        Returns:
            Stripped database name

        Raises:
            ValueError: If database is empty after stripping
        """
        if not v or not v.strip():
            raise ValueError("database no puede estar vacío")

        return v.strip()

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, v: str | None) -> str | None:
        """Strip whitespace from username."""
        if v is None:
            return None

        stripped = v.strip()
        if stripped == "":
            raise ValueError("username no puede estar vacío")

        return stripped

    @field_validator("password", mode="before")
    @classmethod
    def strip_password(cls, v: str | None) -> str | None:
        """Strip whitespace from password.

        Note: Password validation is now delegated to model_validator
        to handle engine-specific rules (e.g., CockroachDB allows empty).
        """
        if v is None:
            return None

        stripped = v.strip()
        return stripped if stripped else ""

    @model_validator(mode="after")
    def validate_password_by_engine(self) -> ConnectionConfig:
        """Validate password based on engine type.

        CockroachDB allows empty password (uses root without auth in docker).
        Other engines require non-empty password.

        Raises:
            ValueError: If password is empty for engines that require it
        """
        engine = (self.engine or "").lower()

        # CockroachDB allows empty password (typical in docker/local dev)
        if engine in {"cockroachdb", "cockroach"}:
            return self

        # SQLite also allows empty/None password (file-based, no auth)
        if engine == "sqlite":
            return self

        # For other engines, enforce non-empty password if username is provided
        # (password might be None for no-auth scenarios, but if provided, can't be empty)
        if self.password is not None and self.password == "":
            raise ValueError("password no puede estar vacío")

        return self

    @field_validator("port", mode="before")
    @classmethod
    def validate_port(cls, v: int | None, info: ValidationInfo) -> int | None:
        """Validate port number and set defaults based on engine.

        Args:
            v: Port number if provided
            info: Validation context with engine information

        Returns:
            Default port for engine or provided value

        Raises:
            ValueError: If port is out of valid range (1-65535)
        """
        if v is not None:
            if v <= 0 or v > 65535:
                raise ValueError("Puerto debe estar entre 1 y 65535")
            return v

        engine = info.data.get("engine", "").lower()
        if engine == "mongodb":
            return 27017
        elif engine == "postgresql":
            return 5432
        elif engine == "mysql":
            return 3306
        elif engine == "redis":
            return 6379
        elif engine == "neo4j":
            return 7687
        elif engine == "elasticsearch":
            return 9200
        elif engine == "sqlite":
            return None
        elif engine == "dynamodb":
            return None
        return v

    def model_post_init(self, __context: Any) -> None:
        """Configure database-specific settings after initialization.

        Automatically sets authSource to 'admin' for MongoDB if username is provided.

        Args:
            __context: Pydantic context (unused)
        """
        if self.engine.lower() == "mongodb":
            if self.username and not self.extra.get("authSource"):
                self.extra["authSource"] = "admin"


class PlanNode(BaseModel):
    """Nodo del árbol de ejecución - agnóstico al motor.

    Estructura jerárquica que representa planes de cualquier BD:
    - SQL: Seq Scan → Index Scan → Join → Sort
    - NoSQL: COLLSCAN → IXSCAN → Group → Output
    - Neo4j: ProduceResults → Apply → NodeIndexSeek
    - InfluxDB: range → filter → group → aggregation

    Ejemplos de properties por motor:
    - PostgreSQL: table_name, index_name, filter_condition, buffers
    - MongoDB: stage, collection, input_docs, output_docs
    - Neo4j: operator, operands, rows_created
    - InfluxDB: bucket_name, time_range, function
    """

    node_type: str
    """Tipo de operación (Seq Scan, Index Scan, Join, etc.)"""

    cost: float | None = None
    """Costo estimado por el optimizador"""

    estimated_rows: int | None = None
    """Filas que el optimizador predice"""

    actual_rows: int | None = None
    """Filas reales retornadas/procesadas"""

    actual_time_ms: float | None = None
    """Tiempo real de ejecución en ms"""

    children: list[PlanNode] = Field(default_factory=list)
    """Nodos hijo (recursivo)"""

    properties: dict[str, Any] = Field(default_factory=dict)
    """Propiedades específicas: table_name, filter_condition, etc."""

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        """Valida que node_type no esté vacío."""
        if not v or not v.strip():
            raise ValueError("node_type no puede estar vacío")
        return v.strip()


class Warning(BaseModel):
    """Advertencia estructurada - reemplaza strings planos.

    Permite que la TUI tome decisiones visuales basadas en severidad
    sin necesidad de parsear el mensaje.
    """

    severity: Literal["critical", "high", "medium", "low"]
    """
    critical: Error que afecta severamente performance (~score < 40)
    high: Problema significativo (~score 40-60)
    medium: Problema moderado (~score 60-80)
    low: Informativo, mejora recomendada (~score > 80)
    """

    message: str
    """Descripción clara del problema (ej: 'Full table scan on users')

    Debe ser:
    - Conciso (máx 200 caracteres)
    - Accionable (indicar qué está mal)
    - Específico (incluir nombres reales)
    """

    node_type: str | None = None
    """Tipo de nodo afectado (ej: 'Seq Scan', 'COLLSCAN', 'Sort')

    Permite a la TUI colorear el árbol de ejecución.
    """

    affected_object: str | None = None
    """Tabla, colección, índice, campo, etc.

    Ejemplos:
    - PostgreSQL: 'users', 'orders_idx', 'age'
    - MongoDB: 'users', 'email_index'
    - Neo4j: 'User', 'MATCHES_WITH'
    """

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Información adicional específica del detector:

    Ejemplos:
    - {'rows': 50000, 'threshold': 10000}
    - {'actual': 10000, 'estimated': 100, 'divergence': 0.99}
    - {'has_filesort': True, 'function': 'LOWER'}
    """

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Valida que el mensaje no esté vacío."""
        if not v or not v.strip():
            raise ValueError("message no puede estar vacío")
        return v.strip()


class Recommendation(BaseModel):
    """Recomendación priorizada y estructurada.

    Reemplaza strings genéricos con información accionable,
    código ejecutable, y prioridad automática.
    """

    priority: int
    """Prioridad: 1-10 (1=crítico/urgente, 10=futuro/nice-to-have)

    Calculado por cada adapter según:
    - Severidad del problema (critical → 1-2)
    - Impacto en performance (high → 3-4)
    - Complejidad de implementación

    La TUI simplemente ordena de menor a mayor sin entender criterios.
    """

    title: str
    """Título accionable (máx 100 caracteres)

    Ejemplos:
    - "Add index on users(email)"
    - "Rewrite query without LOWER() function"
    - "Add time filter to InfluxDB query"
    - "Use MERGE with MATCH instead of MATCH + CREATE"
    """

    description: str
    """Explicación detallada (máx 500 caracteres)

    Debe incluir:
    - POR QUÉ es necesario
    - CÓMO solucionar
    - BENEFICIOS esperados
    """

    code_snippet: str | None = None
    """Código SQL/Flux/Cypher listo para copiar y ejecutar

    Ejemplos:
    - PostgreSQL: "CREATE INDEX idx_users_email ON users(email);"
    - MongoDB: "db.users.createIndex({'email': 1});"
    - Flux: "range(start: -24h, stop: now())"
    - Neo4j: "CREATE INDEX FOR (u:User) ON (u.email)"

    Si None, no hay snippet disponible.
    """

    affected_object: str | None = None
    """Tabla/colección/índice/campo que se recomienda cambiar

    Permite a CLI/TUI enlazar la recomendación con el object específico.
    """

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Información específica del motor

    Ejemplos:
    - {'type': 'index', 'columns': ['email']}
    - {'alternative_query': '...'}
    - {'execution_time_reduction': '45%'}
    """

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """Valida que priority esté entre 1-10."""
        if not 1 <= v <= 10:
            raise ValueError("priority debe estar entre 1 y 10")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Valida que title no esté vacío."""
        if not v or not v.strip():
            raise ValueError("title no puede estar vacío")
        return v.strip()


class QueryAnalysisReport(BaseModel):
    """Reporte de análisis de consulta - Modelo v2 Estructurado.

    Reemplaza strings planos por dataclasses que preservan
    semántica y permiten TUI agnóstica.

    Attributes:
        engine: Motor de base de datos que ejecutó el análisis
        query: Consulta SQL analizada
        score: Puntuación de optimización (0-100)
        execution_time_ms: Tiempo de ejecución en milisegundos
        warnings: Lista de advertencias estructuradas
        recommendations: Lista de recomendaciones priorizadas
        plan_tree: Árbol jerárquico del plan de ejecución
        analyzed_at: Timestamp UTC de cuándo se realizó el análisis
        raw_plan: Plan de ejecución completo del motor (compatibilidad)
        metrics: Métricas adicionales del plan
    """

    engine: str
    """Motor BD: postgresql, mysql, mongodb, neo4j, influxdb, etc."""

    query: str
    """Consulta original analizada"""

    score: int
    """Puntuación 0-100 (CAMBIO: float → int para mayor precisión)

    Escala:
    - 90-100: Excelente (sin problemas detectados)
    - 70-89: Bueno (problemas menores)
    - 50-69: Aceptable (problemas moderados)
    - 30-49: Pobre (problemas significativos)
    - 0-29: Crítico (optimización urgente)
    """

    execution_time_ms: float
    """Tiempo de ejecución en milisegundos"""

    warnings: list[Warning] = Field(default_factory=list)
    """Advertencias estructuradas - reemplaza list[str]"""

    recommendations: list[Recommendation] = Field(default_factory=list)
    """Recomendaciones priorizadas - reemplaza list[str]"""

    plan_tree: PlanNode | None = None
    """Árbol jerárquico del plan de ejecución

    Construido desde el plan normalizado del parser.
    None si el motor no proporciona plan (ej: Redis).
    """

    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    """Timestamp UTC de cuándo se realizó el análisis

    ✅ IMPORTANTE: Siempre UTC para consistencia global
    Serialización JSON: ISO 8601 format
    """

    raw_plan: dict[str, Any] | None = None
    """Plan original del motor (JSON/dict) - compatibilidad

    Preservado para:
    - Debugging
    - Comparativas futuras
    - Código legacy que lo requiera
    """

    metrics: dict[str, Any] = Field(default_factory=dict)
    """Métricas adicionales específicas del parser

    Ejemplos:
    - PostgreSQL: node_count, buffers_hit, buffers_read
    - MongoDB: examination_ratio, index_scans
    - InfluxDB: bucket_size, transformation_count
    """

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("engine", mode="before")
    @classmethod
    def validate_report_engine(cls, v: str) -> str:
        """Validate and normalize engine name to lowercase.

        Args:
            v: Engine name

        Returns:
            Lowercase engine name

        Raises:
            ValueError: If engine is not supported
        """
        if not v or not v.strip():
            raise ValueError("engine no puede estar vacío")

        engine_lower = v.strip().lower()
        valid_engines = {
            "postgresql",
            "mysql",
            "sqlite",
            "mongodb",
            "redis",
            "neo4j",
            "cockroachdb",
            "yugabytedb",
            "influxdb",
            "dynamodb",
            "cassandra",
            "elasticsearch",
        }

        if engine_lower not in valid_engines:
            raise ValueError("Motor no soportado")

        return engine_lower

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        """Valida que score esté entre 0-100."""
        if not 0 <= v <= 100:
            raise ValueError("Score debe estar entre 0 y 100")
        return v

    @field_validator("execution_time_ms")
    @classmethod
    def validate_execution_time(cls, v: float) -> float:
        """Valida que execution_time_ms sea positivo (> 0).

        Note: 0 is rejected as it indicates a query that took unmeasurable time.
        """
        if v <= 0:
            raise ValueError("execution_time_ms debe ser mayor a 0")
        return v
