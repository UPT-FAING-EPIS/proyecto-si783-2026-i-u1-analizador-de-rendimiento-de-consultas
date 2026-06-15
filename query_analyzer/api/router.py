"""Endpoints de la API FastAPI para el analizador de consultas."""

import logging
from typing import Any

from fastapi import APIRouter

from query_analyzer.adapters import AdapterRegistry
from query_analyzer.adapters.models import AIAnalysisResult, ConnectionConfig, QueryAnalysisReport
from query_analyzer.core import AIAnalyzer
from query_analyzer.core.connection_diagnostics import ConnectionDiagnosticsService

from .schemas import (
    AIAnalyzeRequest,
    AIAnalyzeResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    ConnectionRequest,
    EngineInfoResponse,
    MetricsRequest,
    MetricsResponse,
    SlowQueriesRequest,
)

router = APIRouter(prefix="/analyzer", tags=["Query Analyzer"])
logger = logging.getLogger(__name__)


def _build_config(conn: ConnectionRequest) -> ConnectionConfig:
    """Convierte el schema de API a ConnectionConfig del core."""
    extra: dict[str, Any] = {}
    if conn.auth_database:
        extra["authSource"] = conn.auth_database
    if conn.ssl:
        extra["ssl"] = conn.ssl

    return ConnectionConfig(
        engine=conn.engine,
        host=conn.host,
        port=conn.port,
        username=conn.username,
        password=conn.password.get_secret_value() if conn.password else None,
        database=conn.database,
        extra=extra,
    )


def _log_api_error(
    operation: str,
    error: Exception,
    config: ConnectionConfig | None = None,
    secrets: tuple[str, ...] = (),
) -> None:
    """Log technical API errors without exposing configured secrets."""
    detail = str(error)
    if config is not None:
        detail = ConnectionDiagnosticsService.sanitize_secrets(detail, config)
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, "********")
    logger.error("API operation %s failed: %s", operation, detail)


def _run_optional_ai_analysis(report: QueryAnalysisReport) -> AIAnalysisResult | None:
    """Run configured AI analysis without making factual EXPLAIN depend on it."""
    try:
        analyzer = AIAnalyzer()
        if not analyzer.available:
            return None

        result = analyzer.analyze(
            plan_json=report.raw_plan or report.plan_summary or "No plan available",
            query=report.query,
            engine=report.engine,
        )

        if result is None:
            return None

        return AIAnalysisResult(
            summary=result.summary,
            observations=result.observations,
            recommendations=result.recommendations,
            suggested_query=result.suggested_query,
            raw_response=result.raw_response,
        )
    except Exception as error:
        _log_api_error("explain-ai", error)
        return None


@router.get("/engines")
def list_engines() -> dict[str, list[str]]:
    """Lista todos los motores de BD soportados."""
    return {"engines": AdapterRegistry.list_engines()}


@router.post("/explain", response_model=AnalyzeResponse)
def analyze_query(req: AnalyzeRequest) -> AnalyzeResponse:
    """Ejecuta EXPLAIN en una consulta y retorna el análisis."""
    config: ConnectionConfig | None = None
    try:
        config = _build_config(req.connection)
        adapter = AdapterRegistry.create(req.connection.engine, config)

        with adapter:
            report = adapter.execute_explain(req.query)

        if req.include_ai:
            report.ai_analysis = _run_optional_ai_analysis(report)

        return AnalyzeResponse(
            success=True,
            engine=req.connection.engine,
            query=req.query,
            execution_time_ms=report.execution_time_ms,
            plan_tree=report.plan_tree,
            plan_summary=report.plan_summary,
            ai_analysis=report.ai_analysis,
            analyzed_at=report.analyzed_at,
            raw_plan=report.raw_plan,
            metrics=report.metrics,
        )
    except Exception as error:
        _log_api_error("explain", error, config)
        return AnalyzeResponse(
            success=False,
            engine=req.connection.engine,
            query=req.query,
            error="No se pudo analizar la consulta con la conexión proporcionada.",
        )


@router.post("/ai", response_model=AIAnalyzeResponse)
def ai_analyze(req: AIAnalyzeRequest) -> AIAnalyzeResponse:
    """Analiza un plan EXPLAIN usando IA."""
    try:
        api_key = req.ai_config.api_key.get_secret_value() if req.ai_config else ""
        analyzer = (
            AIAnalyzer(
                base_url=req.ai_config.base_url,
                api_key=api_key,
                model=req.ai_config.model,
            )
            if req.ai_config
            else AIAnalyzer()
        )

        if not analyzer.available:
            return AIAnalyzeResponse(success=False, error="IA no configurada correctamente")

        result = analyzer.analyze(req.plan_json, req.query, req.engine)

        if result is None:
            return AIAnalyzeResponse(success=False, error="Sin respuesta de IA")

        return AIAnalyzeResponse(
            success=True,
            summary=result.summary,
            observations=result.observations,
            recommendations=result.recommendations,
            suggested_query=result.suggested_query,
        )
    except Exception as error:
        secrets = (req.ai_config.api_key.get_secret_value(),) if req.ai_config else ()
        _log_api_error("ai", error, secrets=secrets)
        return AIAnalyzeResponse(success=False, error="No se pudo completar el análisis con IA.")


@router.post("/metrics", response_model=MetricsResponse)
def get_metrics(req: MetricsRequest) -> MetricsResponse:
    """Obtiene métricas del motor de BD."""
    config: ConnectionConfig | None = None
    try:
        config = _build_config(req.connection)
        adapter = AdapterRegistry.create(req.connection.engine, config)

        with adapter:
            metrics = adapter.get_metrics()

        return MetricsResponse(success=True, metrics=metrics)
    except Exception as error:
        _log_api_error("metrics", error, config)
        return MetricsResponse(
            success=False,
            error="No se pudieron obtener las métricas con la conexión proporcionada.",
        )


@router.post("/slow-queries")
def get_slow_queries(req: SlowQueriesRequest) -> dict[str, Any]:
    """Obtiene las consultas lentas del motor."""
    config: ConnectionConfig | None = None
    try:
        config = _build_config(req.connection)
        adapter = AdapterRegistry.create(req.connection.engine, config)

        with adapter:
            queries = adapter.get_slow_queries(req.threshold_ms)

        return {"success": True, "slow_queries": queries}
    except Exception as error:
        _log_api_error("slow-queries", error, config)
        return {
            "success": False,
            "error": "No se pudieron obtener las consultas lentas con la conexión proporcionada.",
        }


@router.post("/engine-info", response_model=EngineInfoResponse)
def get_engine_info(req: MetricsRequest) -> EngineInfoResponse:
    """Obtiene información del motor (versión, config, etc.)."""
    config: ConnectionConfig | None = None
    try:
        config = _build_config(req.connection)
        adapter = AdapterRegistry.create(req.connection.engine, config)

        with adapter:
            info = adapter.get_engine_info()

        return EngineInfoResponse(success=True, info=info)
    except Exception as error:
        _log_api_error("engine-info", error, config)
        return EngineInfoResponse(
            success=False,
            error="No se pudo obtener información del motor con la conexión proporcionada.",
        )
