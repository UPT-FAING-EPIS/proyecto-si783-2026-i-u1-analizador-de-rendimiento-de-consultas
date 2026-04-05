"""
Tests de integración para AntiPatternDetector usando fixtures reales.

Carga fixtures JSON de planes normalizados para PostgreSQL, MySQL y SQLite,
y valida que el detector identifique correctamente los anti-patrones.
"""

import json
from pathlib import Path

import pytest

from query_analyzer.core import AntiPatternDetector


@pytest.fixture
def fixtures_dir():
    """Retorna el directorio donde están los fixtures."""
    return Path(__file__).parent.parent / "fixtures"


class TestPostgreSQLFixtures:
    """Tests de integración con fixtures PostgreSQL."""

    @pytest.fixture
    def pg_fixtures_dir(self, fixtures_dir):
        """Directorio específico de fixtures PostgreSQL."""
        return fixtures_dir / "postgresql"

    def load_fixture(self, fixture_path: Path) -> dict:
        """Carga un fixture JSON."""
        with open(fixture_path) as f:
            return json.load(f)

    def test_postgresql_full_table_scan_detection(self, pg_fixtures_dir):
        """Verifica detección de full_table_scan en PostgreSQL."""
        fixture = self.load_fixture(pg_fixtures_dir / "full_table_scan.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        # Validar anti-patrones esperados
        expected = fixture["expected"]
        detected_names = [ap.name for ap in result.anti_patterns]

        for expected_name in expected["anti_patterns_detected"]:
            assert expected_name in detected_names, (
                f"Anti-patrón '{expected_name}' no detectado. Detectados: {detected_names}"
            )

        # Validar rango de score
        assert expected["min_score"] <= result.score <= expected["max_score"], (
            f"Score {result.score} fuera de rango [{expected['min_score']}, {expected['max_score']}]"
        )

        # Validar recomendaciones
        if expected["should_have_recommendation"]:
            assert len(result.recommendations) > 0, "Se esperan recomendaciones pero no hay"

    def test_postgresql_row_estimation_error_detection(self, pg_fixtures_dir):
        """Verifica detección de row_estimation_error en PostgreSQL."""
        fixture = self.load_fixture(pg_fixtures_dir / "row_estimation_error.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        # Validar que row_estimation_error está en los detectados
        detected_names = [ap.name for ap in result.anti_patterns]
        assert "row_estimation_error" in detected_names, (
            f"row_estimation_error no detectado. Detectados: {detected_names}"
        )

    def test_postgresql_nested_loop_cost_detection(self, pg_fixtures_dir):
        """Verifica detección de nested_loop_cost en PostgreSQL."""
        fixture = self.load_fixture(pg_fixtures_dir / "nested_loop_cost.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        assert "nested_loop_cost" in [ap.name for ap in result.anti_patterns]

    def test_postgresql_result_without_limit_detection(self, pg_fixtures_dir):
        """Verifica detección de result_without_limit en PostgreSQL."""
        fixture = self.load_fixture(pg_fixtures_dir / "result_without_limit.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "result_without_limit" in detected_names

    def test_postgresql_function_in_where_detection(self, pg_fixtures_dir):
        """Verifica detección de function_in_where en PostgreSQL."""
        fixture = self.load_fixture(pg_fixtures_dir / "function_in_where.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "function_in_where" in detected_names

    def test_postgresql_select_star_detection(self, pg_fixtures_dir):
        """Verifica detección de select_star en PostgreSQL."""
        fixture = self.load_fixture(pg_fixtures_dir / "select_star.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        assert "select_star" in [ap.name for ap in result.anti_patterns]
        assert result.score == fixture["expected"]["min_score"]  # Baja severidad

    def test_postgresql_sort_without_index_detection(self, pg_fixtures_dir):
        """Verifica detección de sort_without_index en PostgreSQL."""
        fixture = self.load_fixture(pg_fixtures_dir / "sort_without_index.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "sort_without_index" in detected_names


class TestMySQLFixtures:
    """Tests de integración con fixtures MySQL."""

    @pytest.fixture
    def mysql_fixtures_dir(self, fixtures_dir):
        """Directorio específico de fixtures MySQL."""
        return fixtures_dir / "mysql"

    def load_fixture(self, fixture_path: Path) -> dict:
        """Carga un fixture JSON."""
        with open(fixture_path) as f:
            return json.load(f)

    def test_mysql_full_table_scan_detection(self, mysql_fixtures_dir):
        """Verifica detección de full_table_scan en MySQL."""
        fixture = self.load_fixture(mysql_fixtures_dir / "full_table_scan.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        expected = fixture["expected"]
        detected_names = [ap.name for ap in result.anti_patterns]

        for expected_name in expected["anti_patterns_detected"]:
            assert expected_name in detected_names, (
                f"Anti-patrón '{expected_name}' no detectado en MySQL"
            )

    def test_mysql_row_estimation_error_detection(self, mysql_fixtures_dir):
        """Verifica detección de row_estimation_error en MySQL."""
        fixture = self.load_fixture(mysql_fixtures_dir / "row_estimation_error.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        assert "row_estimation_error" in [ap.name for ap in result.anti_patterns]

    def test_mysql_nested_loop_cost_detection(self, mysql_fixtures_dir):
        """Verifica detección de nested_loop_cost en MySQL."""
        fixture = self.load_fixture(mysql_fixtures_dir / "nested_loop_cost.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        assert "nested_loop_cost" in [ap.name for ap in result.anti_patterns]

    def test_mysql_result_without_limit_detection(self, mysql_fixtures_dir):
        """Verifica detección de result_without_limit en MySQL."""
        fixture = self.load_fixture(mysql_fixtures_dir / "result_without_limit.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "result_without_limit" in detected_names

    def test_mysql_function_in_where_detection(self, mysql_fixtures_dir):
        """Verifica detección de function_in_where en MySQL."""
        fixture = self.load_fixture(mysql_fixtures_dir / "function_in_where.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "function_in_where" in detected_names

    def test_mysql_select_star_detection(self, mysql_fixtures_dir):
        """Verifica detección de select_star en MySQL."""
        fixture = self.load_fixture(mysql_fixtures_dir / "select_star.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        assert "select_star" in [ap.name for ap in result.anti_patterns]

    def test_mysql_sort_without_index_detection(self, mysql_fixtures_dir):
        """Verifica detección de sort_without_index en MySQL."""
        fixture = self.load_fixture(mysql_fixtures_dir / "sort_without_index.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "sort_without_index" in detected_names


class TestSQLiteFixtures:
    """Tests de integración con fixtures SQLite."""

    @pytest.fixture
    def sqlite_fixtures_dir(self, fixtures_dir):
        """Directorio específico de fixtures SQLite."""
        return fixtures_dir / "sqlite"

    def load_fixture(self, fixture_path: Path) -> dict:
        """Carga un fixture JSON."""
        with open(fixture_path) as f:
            return json.load(f)

    def test_sqlite_full_table_scan_detection(self, sqlite_fixtures_dir):
        """Verifica detección de full_table_scan en SQLite."""
        fixture = self.load_fixture(sqlite_fixtures_dir / "full_table_scan.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        expected = fixture["expected"]
        detected_names = [ap.name for ap in result.anti_patterns]

        for expected_name in expected["anti_patterns_detected"]:
            assert expected_name in detected_names

    def test_sqlite_result_without_limit_detection(self, sqlite_fixtures_dir):
        """Verifica detección de result_without_limit en SQLite."""
        fixture = self.load_fixture(sqlite_fixtures_dir / "result_without_limit.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "result_without_limit" in detected_names

    def test_sqlite_select_star_detection(self, sqlite_fixtures_dir):
        """Verifica detección de select_star en SQLite."""
        fixture = self.load_fixture(sqlite_fixtures_dir / "select_star.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        assert "select_star" in [ap.name for ap in result.anti_patterns]

    def test_sqlite_function_in_where_detection(self, sqlite_fixtures_dir):
        """Verifica detección de function_in_where en SQLite."""
        fixture = self.load_fixture(sqlite_fixtures_dir / "function_in_where.json")

        detector = AntiPatternDetector()
        result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

        detected_names = [ap.name for ap in result.anti_patterns]
        assert "function_in_where" in detected_names


class TestReproducibility:
    """Tests para verificar reproducibilidad de resultados."""

    def load_fixture(self, fixture_path: Path) -> dict:
        """Carga un fixture JSON."""
        with open(fixture_path) as f:
            return json.load(f)

    def test_same_plan_same_score(self, fixtures_dir):
        """Mismo plan = mismo score (reproducibilidad)."""
        fixture_path = fixtures_dir / "postgresql" / "full_table_scan.json"
        fixture = self.load_fixture(fixture_path)

        # Ejecuta el análisis 3 veces
        scores = []
        for _ in range(3):
            detector = AntiPatternDetector()
            result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))
            scores.append(result.score)

        # Todos los scores deben ser iguales
        assert scores[0] == scores[1] == scores[2], f"Scores inconsistentes: {scores}"

    def test_same_plan_same_anti_patterns(self, fixtures_dir):
        """Mismo plan = mismos anti-patrones (reproducibilidad)."""
        fixture_path = fixtures_dir / "postgresql" / "nested_loop_cost.json"
        fixture = self.load_fixture(fixture_path)

        # Ejecuta el análisis 2 veces
        results = []
        for _ in range(2):
            detector = AntiPatternDetector()
            result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))
            results.append(sorted([ap.name for ap in result.anti_patterns]))

        # Los anti-patrones deben ser los mismos
        assert results[0] == results[1], (
            f"Anti-patrones inconsistentes: {results[0]} vs {results[1]}"
        )


class TestCrossEngine:
    """Tests para comparar comportamiento entre engines."""

    def load_fixture(self, fixture_path: Path) -> dict:
        """Carga un fixture JSON."""
        with open(fixture_path) as f:
            return json.load(f)

    def test_full_table_scan_detected_all_engines(self, fixtures_dir):
        """full_table_scan debe detectarse en los 3 engines."""
        detections = {}

        for engine in ["postgresql", "mysql", "sqlite"]:
            fixture_path = fixtures_dir / engine / "full_table_scan.json"
            fixture = self.load_fixture(fixture_path)

            detector = AntiPatternDetector()
            result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

            detected = [ap.name for ap in result.anti_patterns]
            detections[engine] = detected

        # Todos deben detectar al menos full_table_scan
        for engine, detected in detections.items():
            assert "full_table_scan" in detected, f"full_table_scan no detectado en {engine}"

    def test_select_star_detected_all_engines(self, fixtures_dir):
        """select_star debe detectarse en los 3 engines."""
        detections = {}

        for engine in ["postgresql", "mysql", "sqlite"]:
            fixture_path = fixtures_dir / engine / "select_star.json"
            fixture = self.load_fixture(fixture_path)

            detector = AntiPatternDetector()
            result = detector.analyze(fixture["normalized_plan"], fixture.get("query", ""))

            detected = [ap.name for ap in result.anti_patterns]
            detections[engine] = detected

        # Todos deben detectar select_star
        for engine, detected in detections.items():
            assert "select_star" in detected, f"select_star no detectado en {engine}"
