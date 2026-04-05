"""Modelos de datos para la configuración y análisis de conexiones."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConnectionConfig(BaseModel):
    """Configuración para establecer conexión con una base de datos.

    Attributes:
        engine: Motor de base de datos (mysql, postgresql, sqlite)
        host: Dirección del servidor (path para SQLite)
        port: Puerto de conexión (1-65535, opcional para SQLite)
        database: Nombre de la base de datos
        username: Usuario para autenticación (opcional para SQLite)
        password: Contraseña para autenticación (opcional para SQLite)
        extra: Parámetros adicionales específicos del motor
    """

    engine: str
    host: str
    port: int
    database: str
    username: str
    password: str
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Valida que el motor sea uno de los soportados."""
        valid_engines = {"mysql", "postgresql", "sqlite"}
        engine_lower = v.lower()
        if engine_lower not in valid_engines:
            raise ValueError(
                f"Motor no soportado: {v}. Opciones válidas: {', '.join(valid_engines)}"
            )
        return engine_lower

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int, info) -> int:  # type: ignore[no-untyped-def]
        """Valida que el puerto esté en rango válido. SQLite permite puerto 0."""
        engine = info.data.get("engine", "").lower() if hasattr(info, "data") else ""
        if engine == "sqlite":
            return v
        if not (1 <= v <= 65535):
            raise ValueError(f"Puerto debe estar entre 1 y 65535, recibido: {v}")
        return v

    @field_validator("host", "database", "username", "password")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        """Valida que los campos requeridos no estén vacíos. SQLite permite valores vacíos."""
        engine = info.data.get("engine", "").lower() if hasattr(info, "data") else ""
        if engine == "sqlite":
            return v.strip() if v else ""
        if not v or not v.strip():
            raise ValueError("Campo requerido no puede estar vacío")
        return v.strip()


class QueryAnalysisReport(BaseModel):
    """Reporte de análisis de una consulta SQL.

    Attributes:
        engine: Motor que ejecutó el análisis
        query: Consulta SQL analizada
        score: Puntuación de optimización (0-100, donde 100 es óptimo)
        execution_time_ms: Tiempo de ejecución en milisegundos
        warnings: Lista de advertencias encontradas
        recommendations: Recomendaciones de optimización
        raw_plan: Plan de ejecución crudo del motor (JSON, dict, string)
        metrics: Métricas específicas del motor
    """

    engine: str
    query: str
    score: int
    execution_time_ms: float
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    raw_plan: Any
    metrics: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Valida que el motor sea uno de los soportados."""
        valid_engines = {"mysql", "postgresql", "sqlite"}
        engine_lower = v.lower()
        if engine_lower not in valid_engines:
            raise ValueError(
                f"Motor no soportado: {v}. Opciones válidas: {', '.join(valid_engines)}"
            )
        return engine_lower

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        """Valida que el score esté en rango válido (0-100)."""
        if not (0 <= v <= 100):
            raise ValueError(f"Score debe estar entre 0 y 100, recibido: {v}")
        return v

    @field_validator("execution_time_ms")
    @classmethod
    def validate_execution_time(cls, v: float, info: Any) -> float:
        """Valida que el tiempo de ejecución sea positivo. SQLite permite 0."""
        engine = info.data.get("engine", "").lower() if hasattr(info, "data") else ""
        if engine == "sqlite":
            return v
        if v <= 0:
            raise ValueError(f"execution_time_ms debe ser mayor a 0, recibido: {v}")
        return v
