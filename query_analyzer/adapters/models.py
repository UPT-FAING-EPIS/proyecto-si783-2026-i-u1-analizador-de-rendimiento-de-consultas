"""Modelos de datos para adapters de bases de datos."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectionConfig(BaseModel):
    """Configuración de conexión a una base de datos.

    Attributes:
        engine: Motor de base de datos (postgresql, mysql, sqlite)
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
