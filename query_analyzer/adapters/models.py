"""Modelos de datos para la configuración y análisis de conexiones."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConnectionConfig(BaseModel):  # type: ignore[misc]
    """
    Configuración para establecer conexión con una base de datos.

    Attributes:
        engine: Motor de base de datos (mysql, postgresql)
        host: Dirección del servidor
        port: Puerto de conexión (1-65535)
        database: Nombre de la base de datos
        username: Usuario para autenticación
        password: Contraseña para autenticación
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

    @field_validator("engine")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Valida que el motor sea uno de los soportados."""
        valid_engines = {"mysql", "postgresql"}
        engine_lower = v.lower()
        if engine_lower not in valid_engines:
            raise ValueError(
                f"Motor no soportado: {v}. Opciones válidas: {', '.join(valid_engines)}"
            )
        return engine_lower

    @field_validator("port")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Valida que el puerto esté en rango válido."""
        if not (1 <= v <= 65535):
            raise ValueError(f"Puerto debe estar entre 1 y 65535, recibido: {v}")
        return v

    @field_validator("host", "database", "username", "password")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Valida que los campos requeridos no estén vacíos."""
        if not v or not v.strip():
            raise ValueError("Campo requerido no puede estar vacío")
        return v.strip()


class QueryAnalysisReport(BaseModel):  # type: ignore[misc]
    """
    Reporte de análisis de una consulta SQL.

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

    @field_validator("engine")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Valida que el motor sea uno de los soportados."""
        valid_engines = {"mysql", "postgresql"}
        engine_lower = v.lower()
        if engine_lower not in valid_engines:
            raise ValueError(
                f"Motor no soportado: {v}. Opciones válidas: {', '.join(valid_engines)}"
            )
        return engine_lower

    @field_validator("score")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_score(cls, v: int) -> int:
        """Valida que el score esté en rango válido (0-100)."""
        if not (0 <= v <= 100):
            raise ValueError(f"Score debe estar entre 0 y 100, recibido: {v}")
        return v

    @field_validator("execution_time_ms")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_execution_time(cls, v: float) -> float:
        """Valida que el tiempo de ejecución sea positivo."""
        if v <= 0:
            raise ValueError(f"execution_time_ms debe ser mayor a 0, recibido: {v}")
        return v
