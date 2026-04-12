"""Modelos de datos para adapters de bases de datos."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class ConnectionConfig(BaseModel):
    """Configuración de conexión a una base de datos.

    Attributes:
        engine: Motor de base de datos (postgresql, mysql, sqlite, mongodb)
        host: Dirección del servidor (optional for SQLite)
        port: Puerto de conexión (optional for SQLite)
        database: Nombre o ruta de la base de datos
        username: Usuario para autenticación (optional for SQLite)
        password: Contraseña para autenticación (optional for SQLite)
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

    @field_validator("port", mode="before")
    @classmethod
    def set_default_port(cls, v: int | None, info: ValidationInfo) -> int | None:
        """Set default port based on database engine.

        Args:
            v: Port number if provided
            info: Validation context with engine information

        Returns:
            Default port for engine or provided value
        """
        if v is not None:
            return v

        engine = info.data.get("engine", "").lower()
        if engine == "mongodb":
            return 27017
        elif engine == "postgresql":
            return 5432
        elif engine == "mysql":
            return 3306
        elif engine == "sqlite":
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


class QueryAnalysisReport(BaseModel):
    """Reporte de análisis de una consulta SQL.

    Attributes:
        engine: Motor de base de datos que ejecutó el análisis
        query: Consulta SQL analizada
        score: Puntuación de optimización (0-100)
        execution_time_ms: Tiempo de ejecución en milisegundos
        warnings: Lista de advertencias encontradas
        recommendations: Lista de recomendaciones de optimización
        raw_plan: Plan de ejecución completo del motor
        metrics: Métricas adicionales del plan
    """

    engine: str
    query: str
    score: float
    execution_time_ms: float
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    raw_plan: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(validate_assignment=True)
