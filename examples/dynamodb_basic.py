#!/usr/bin/env python3
"""Basic DynamoDB Query Analysis Example.

Este script muestra cómo analizar una consulta DynamoDB simple
y obtener métricas de rendimiento básicas.

Uso:
    uv run python examples/dynamodb_basic.py
"""

import json

from query_analyzer.adapters.models import ConnectionConfig
from query_analyzer.adapters.registry import AdapterRegistry


def main() -> None:
    """Analizar una consulta DynamoDB básica."""
    # Configuración de conexión a DynamoDB local (para desarrollo)
    config = ConnectionConfig(
        engine="dynamodb",
        host="http://localhost:8000",  # DynamoDB local endpoint
        database="default",  # Requerido pero no usado en DynamoDB
        username="local",  # Mapea a aws_access_key_id
        password="local",  # Mapea a aws_secret_access_key
    )

    try:
        # Crear adapter y conectar
        adapter = AdapterRegistry.create("dynamodb", config)
        print("✓ Conectado a DynamoDB")

        # Ejemplo 1: Query simple (BUENA PRÁCTICA)
        good_query = {
            "TableName": "Users",
            "KeyConditionExpression": "userId = :id",
            "ExpressionAttributeValues": {":id": {"S": "user123"}},
            "ProjectionExpression": "userId,userName,email",
            "Limit": 10,
        }

        print("\n--- Query: Buena Práctica ---")
        report = adapter.execute_explain(json.dumps(good_query))
        print(f"Score: {report.score}/100")
        if report.warnings:
            for warning in report.warnings:
                print(f"  ⚠ [{warning.severity.upper()}] {warning.message}")
        else:
            print("  ✓ Sin advertencias")

        # Ejemplo 2: Query con anti-pattern (FULL TABLE SCAN)
        bad_query = {
            "TableName": "Users",
            "FilterExpression": "userName = :name",
            "ExpressionAttributeValues": {":name": {"S": "John"}},
        }

        print("\n--- Query: Con Anti-Pattern (Full Scan) ---")
        report = adapter.execute_explain(json.dumps(bad_query))
        print(f"Score: {report.score}/100")
        if report.warnings:
            for warning in report.warnings:
                print(f"  ⚠ [{warning.severity.upper()}] {warning.message}")

        # Mostrar métricas
        print("\n--- Métricas ---")
        if report.metrics:
            for key, value in report.metrics.items():
                print(f"  {key}: {value}")

    except ConnectionError as e:
        print(f"✗ Error de conexión: {e}")
        print("  Nota: Asegúrate de que DynamoDB local esté corriendo")
        print("  O usa AWS credentials para conectarse a DynamoDB en la nube")

    except Exception as e:
        print(f"✗ Error durante el análisis: {e}")
        raise


if __name__ == "__main__":
    main()
