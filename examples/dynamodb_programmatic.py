#!/usr/bin/env python3
"""Programmatic DynamoDB Analysis Example.

Este script muestra cómo realizar análisis por lotes, exportar resultados
a CSV y generar estadísticas agregadas de múltiples queries.

Uso:
    uv run python examples/dynamodb_programmatic.py
"""

import csv
import json
from datetime import datetime
from typing import Any

from query_analyzer.adapters.models import ConnectionConfig
from query_analyzer.adapters.registry import AdapterRegistry


def export_results_to_csv(
    results: list[dict[str, Any]], output_file: str = "query_analysis_results.csv"
) -> None:
    """Exportar resultados de análisis a CSV."""
    if not results:
        print("✗ No hay resultados para exportar")
        return

    try:
        with open(output_file, mode="w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "query_id",
                "table_name",
                "score",
                "has_warnings",
                "warning_count",
                "recommendation_count",
                "execution_time_ms",
                "severity_level",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                warnings: list[Any] = result.get("warnings", [])
                recommendations: list[Any] = result.get("recommendations", [])
                writer.writerow(
                    {
                        "query_id": result.get("query_id"),
                        "table_name": result.get("table_name"),
                        "score": result.get("score"),
                        "has_warnings": "Yes" if warnings else "No",
                        "warning_count": len(warnings),
                        "recommendation_count": len(recommendations),
                        "execution_time_ms": result.get("execution_time_ms"),
                        "severity_level": result.get("severity_level"),
                    }
                )

        print(f"✓ Resultados exportados a: {output_file}")

    except OSError as e:
        print(f"✗ Error al escribir CSV: {e}")


def calculate_statistics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcular estadísticas agregadas de los resultados."""
    if not results:
        return {}

    scores = [r.get("score", 0) for r in results]
    warning_counts = [len(r.get("warnings", [])) for r in results]

    return {
        "total_queries": len(results),
        "average_score": sum(scores) / len(scores),
        "min_score": min(scores),
        "max_score": max(scores),
        "queries_with_warnings": sum(1 for r in results if r.get("warnings")),
        "average_warnings": sum(warning_counts) / len(results) if results else 0,
        "optimization_candidates": sum(1 for r in results if r.get("score", 100) < 80),
    }


def analyze_batch_queries() -> None:
    """Analizar un lote de queries DynamoDB."""
    config = ConnectionConfig(
        engine="dynamodb",
        host="http://localhost:8000",
        database="default",
        username="local",
        password="local",
    )

    # Definir lote de queries para analizar
    queries = [
        {
            "query_id": "q1_good",
            "table_name": "Users",
            "query": {
                "TableName": "Users",
                "KeyConditionExpression": "userId = :id",
                "ExpressionAttributeValues": {":id": {"S": "user123"}},
                "ProjectionExpression": "userId,userName,email",
                "Limit": 10,
            },
        },
        {
            "query_id": "q2_scan",
            "table_name": "Users",
            "query": {
                "TableName": "Users",
                "FilterExpression": "status = :s",
                "ExpressionAttributeValues": {":s": {"S": "ACTIVE"}},
                # Sin Limit ni ProjectionExpression
            },
        },
        {
            "query_id": "q3_no_projection",
            "table_name": "Orders",
            "query": {
                "TableName": "Orders",
                "KeyConditionExpression": "customerId = :cid",
                "ExpressionAttributeValues": {":cid": {"S": "cust456"}},
                # Sin ProjectionExpression - traerá todos los atributos
            },
        },
        {
            "query_id": "q4_gsi_no_range",
            "table_name": "Orders",
            "query": {
                "TableName": "Orders",
                "IndexName": "status-date-index",
                "KeyConditionExpression": "orderStatus = :status",
                "ExpressionAttributeValues": {":status": {"S": "SHIPPED"}},
                # GSI sin Range Key
            },
        },
        {
            "query_id": "q5_optimized_gsi",
            "table_name": "Orders",
            "query": {
                "TableName": "Orders",
                "IndexName": "status-date-index",
                "KeyConditionExpression": "orderStatus = :status AND orderDate > :date",
                "ExpressionAttributeValues": {
                    ":status": {"S": "SHIPPED"},
                    ":date": {"N": "1609459200"},
                },
                "ProjectionExpression": "orderId,orderDate,totalAmount",
                "Limit": 50,
            },
        },
    ]

    results = []

    try:
        adapter = AdapterRegistry.create("dynamodb", config)
        print("✓ Conectado a DynamoDB")
        print(f"\n📊 Analizando {len(queries)} queries...")

        for item in queries:
            try:
                query_id = item["query_id"]
                table_name = item["table_name"]
                query = item["query"]

                print(f"\n  Analizando {query_id}...", end=" ")

                report = adapter.execute_explain(json.dumps(query))

                # Determinar nivel de severidad
                if report.score >= 85:
                    severity = "LOW"
                elif report.score >= 70:
                    severity = "MEDIUM"
                else:
                    severity = "HIGH"

                result: dict[str, Any] = {
                    "query_id": query_id,
                    "table_name": table_name,
                    "score": report.score,
                    "warnings": list(report.warnings),
                    "recommendations": list(report.recommendations),
                    "metrics": report.metrics,
                    "execution_time_ms": report.execution_time_ms,
                    "severity_level": severity,
                }

                results.append(result)
                print(f"✓ Score: {report.score}/100 ({severity})")

            except Exception as e:
                print(f"✗ Error: {e}")

        # Mostrar resultados
        print("\n" + "=" * 60)
        print("RESULTADOS DEL ANÁLISIS POR LOTES")
        print("=" * 60)

        for result in results:
            print(f"\n{result['query_id']} (Tabla: {result['table_name']})")
            print(f"  Score: {result['score']}/100 | Severidad: {result['severity_level']}")
            warnings_list: list[Any] = result["warnings"]
            recommendations_list: list[Any] = result["recommendations"]
            print(
                f"  Advertencias: {len(warnings_list)} | Recomendaciones: {len(recommendations_list)}"
            )

        # Estadísticas agregadas
        stats = calculate_statistics(results)

        print("\n" + "=" * 60)
        print("ESTADÍSTICAS AGREGADAS")
        print("=" * 60)
        print(f"Total de queries analizadas:        {stats.get('total_queries')}")
        print(f"Score promedio:                     {stats.get('average_score'):.2f}/100")
        print(
            f"Score mínimo/máximo:                {stats.get('min_score')}/{stats.get('max_score')}"
        )
        print(f"Queries con advertencias:           {stats.get('queries_with_warnings')}")
        print(f"Promedio de advertencias:           {stats.get('average_warnings'):.2f}")
        print(f"Candidatos a optimización (<80):    {stats.get('optimization_candidates')}")

        # Exportar a CSV
        print("\n" + "=" * 60)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = f"query_analysis_results_{timestamp}.csv"
        export_results_to_csv(results, csv_file)

        # Guardar reporte JSON completo
        json_file = f"query_analysis_report_{timestamp}.json"
        try:
            with open(json_file, "w", encoding="utf-8") as f:
                json_data = {
                    "timestamp": datetime.now().isoformat(),
                    "statistics": stats,
                    "results": [
                        {
                            "query_id": r["query_id"],
                            "table_name": r["table_name"],
                            "score": r["score"],
                            "warning_count": len(r["warnings"]),
                            "recommendation_count": len(r["recommendations"]),
                            "severity_level": r["severity_level"],
                        }
                        for r in results
                    ],
                }
                json.dump(json_data, f, indent=2)
            print(f"✓ Reporte guardado en: {json_file}")
        except OSError as e:
            print(f"✗ Error al escribir JSON: {e}")

    except ConnectionError as e:
        print(f"✗ Error de conexión: {e}")
    except Exception as e:
        print(f"✗ Error durante el análisis: {e}")
        raise


def main() -> None:
    """Ejecutar análisis por lotes."""
    analyze_batch_queries()


if __name__ == "__main__":
    main()
