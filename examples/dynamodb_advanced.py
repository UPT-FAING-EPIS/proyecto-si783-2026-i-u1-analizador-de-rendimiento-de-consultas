#!/usr/bin/env python3
"""Advanced DynamoDB Query Analysis Example.

Este script muestra cómo trabajar con recomendaciones detalladas
y optimizar consultas DynamoDB basándose en métricas de rendimiento.

Uso:
    uv run python examples/dynamodb_advanced.py
"""

import json

from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry


def print_detailed_report(report: QueryAnalysisReport) -> None:
    """Imprimir un reporte detallado con warnings y recomendaciones."""
    print(f"\n{'=' * 60}")
    print(f"SCORE: {report.score}/100")
    print(f"{'=' * 60}")

    # Warnings
    if report.warnings:
        print(f"\n⚠️  ADVERTENCIAS ({len(report.warnings)}):")
        for i, warning in enumerate(report.warnings, 1):
            print(f"\n  {i}. {warning.message}")
            print(f"     Severidad: {warning.severity.upper()}")
            if warning.affected_object:
                print(f"     Afecta a: {warning.affected_object}")
    else:
        print("\n✓ Sin advertencias - Query optimizada")

    # Recommendations
    if report.recommendations:
        print(f"\n💡 RECOMENDACIONES ({len(report.recommendations)}):")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"\n  {i}. [Prioridad {rec.priority}/10] {rec.title}")
            print(f"     {rec.description}")
            if rec.code_snippet:
                print(f"     Código: {rec.code_snippet}")
            if rec.metadata.get("execution_time_reduction"):
                print(f"     Mejora: {rec.metadata['execution_time_reduction']}")

    # Metrics
    if report.metrics:
        print("\n📊 MÉTRICAS:")
        for key, value in report.metrics.items():
            print(f"  • {key}: {value}")


def analyze_query_patterns() -> None:
    """Analizar diferentes patrones de queries con recomendaciones."""
    config = ConnectionConfig(
        engine="dynamodb",
        host="http://localhost:8000",
        database="default",
        username="local",
        password="local",
    )

    try:
        adapter = AdapterRegistry.create("dynamodb", config)
        print("✓ Conectado a DynamoDB")

        # Pattern 1: Query sin ProjectionExpression (Anti-pattern)
        print("\n" + "=" * 60)
        print("PATTERN 1: Query sin ProjectionExpression (Proyección Completa)")
        print("=" * 60)

        query1 = {
            "TableName": "Orders",
            "KeyConditionExpression": "customerId = :cid",
            "ExpressionAttributeValues": {":cid": {"S": "cust123"}},
            # SIN ProjectionExpression - traerá todos los atributos
        }

        report1 = adapter.execute_explain(json.dumps(query1))
        print_detailed_report(report1)

        # Pattern 2: Query con Limit y ProjectionExpression (BUENA PRÁCTICA)
        print("\n" + "=" * 60)
        print("PATTERN 2: Query Optimizada con Limit y ProjectionExpression")
        print("=" * 60)

        query2 = {
            "TableName": "Orders",
            "KeyConditionExpression": "customerId = :cid",
            "ExpressionAttributeValues": {":cid": {"S": "cust123"}},
            "ProjectionExpression": "orderId,orderDate,totalAmount",
            "Limit": 25,
        }

        report2 = adapter.execute_explain(json.dumps(query2))
        print_detailed_report(report2)

        # Pattern 3: Query en GSI sin Range Key (Anti-pattern)
        print("\n" + "=" * 60)
        print("PATTERN 3: Query en GSI sin Range Key")
        print("=" * 60)

        query3 = {
            "TableName": "Orders",
            "IndexName": "status-index",
            "KeyConditionExpression": "orderStatus = :status",
            "ExpressionAttributeValues": {":status": {"S": "PENDING"}},
        }

        report3 = adapter.execute_explain(json.dumps(query3))
        print_detailed_report(report3)

        # Comparación de Scores
        print("\n" + "=" * 60)
        print("COMPARACIÓN DE SCORES")
        print("=" * 60)
        print(f"Pattern 1 (Sin Proyección):         {report1.score}/100")
        print(f"Pattern 2 (Optimizado):             {report2.score}/100")
        print(f"Pattern 3 (GSI sin Range Key):      {report3.score}/100")
        print(f"\nMejora (Pattern 2 vs Pattern 1):   +{report2.score - report1.score} puntos")

    except ConnectionError as e:
        print(f"✗ Error de conexión: {e}")
    except Exception as e:
        print(f"✗ Error durante el análisis: {e}")
        raise


def main() -> None:
    """Ejecutar ejemplo avanzado."""
    analyze_query_patterns()


if __name__ == "__main__":
    main()
