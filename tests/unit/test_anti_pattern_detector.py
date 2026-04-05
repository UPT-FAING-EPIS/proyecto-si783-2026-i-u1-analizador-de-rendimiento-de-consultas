"""
Tests unitarios para AntiPatternDetector.

Prueba los componentes básicos:
- ScoringEngine
- RecommendationEngine
- AntiPatternDetector (métodos de detección)
"""

from query_analyzer.core import (
    AntiPatternDetector,
    DetectorConfig,
    RecommendationEngine,
    ScoringEngine,
    Severity,
)


class TestScoringEngine:
    """Tests para ScoringEngine."""

    def test_initial_score(self):
        """Score inicial debe ser 100."""
        engine = ScoringEngine()
        assert engine.get_score() == 100

    def test_deduct_high_severity(self):
        """Deducción de severidad ALTA: -25."""
        engine = ScoringEngine()
        engine.deduct("full_table_scan", Severity.HIGH)
        assert engine.get_score() == 75

    def test_deduct_medium_severity(self):
        """Deducción de severidad MEDIA: -15."""
        engine = ScoringEngine()
        engine.deduct("row_estimation_error", Severity.MEDIUM)
        assert engine.get_score() == 85

    def test_deduct_low_severity(self):
        """Deducción de severidad BAJA: -5."""
        engine = ScoringEngine()
        engine.deduct("select_star", Severity.LOW)
        assert engine.get_score() == 95

    def test_multiple_deductions(self):
        """Múltiples deduciones acumulan correctamente."""
        engine = ScoringEngine()
        engine.deduct("full_table_scan", Severity.HIGH)  # -25
        engine.deduct("row_estimation_error", Severity.MEDIUM)  # -15
        engine.deduct("select_star", Severity.LOW)  # -5
        assert engine.get_score() == 55

    def test_score_never_negative(self):
        """Score nunca puede ser menor a 0."""
        engine = ScoringEngine()
        for _ in range(10):
            engine.deduct("test", Severity.HIGH)
        assert engine.get_score() == 0

    def test_custom_deduction_amount(self):
        """Permite deducción personalizada."""
        engine = ScoringEngine()
        engine.deduct("custom", Severity.HIGH, amount=10)
        assert engine.get_score() == 90

    def test_reset(self):
        """Reset restaura el score inicial."""
        engine = ScoringEngine()
        engine.deduct("test", Severity.HIGH)
        assert engine.get_score() == 75
        engine.reset()
        assert engine.get_score() == 100


class TestRecommendationEngine:
    """Tests para RecommendationEngine."""

    def test_full_table_scan_recommendation(self):
        """Recomendación de full_table_scan incluye nombre de tabla."""
        rec = RecommendationEngine.full_table_scan("customers", 50000)
        assert "customers" in rec
        assert "50,000" in rec
        assert "Crear índice" in rec

    def test_row_estimation_error_recommendation(self):
        """Recomendación incluye valores reales."""
        rec = RecommendationEngine.row_estimation_error("orders", 45000, 20000, 77.5)
        assert "orders" in rec
        assert "45,000" in rec
        assert "20,000" in rec
        assert "77.5" in rec

    def test_nested_loop_cost_recommendation(self):
        """Recomendación menciona iteraciones."""
        rec = RecommendationEngine.nested_loop_cost(150000, "orders", "items")
        assert "150,000" in rec
        assert "orders" in rec
        assert "items" in rec

    def test_result_without_limit_recommendation(self):
        """Recomendación específica para falta de LIMIT."""
        rec = RecommendationEngine.result_without_limit("users", 100000)
        assert "100,000" in rec
        assert "users" in rec
        assert "LIMIT" in rec

    def test_function_in_where_recommendation(self):
        """Recomendación menciona función y columna."""
        rec = RecommendationEngine.function_in_where("LOWER", "email", "users")
        assert "LOWER" in rec
        assert "email" in rec
        assert "users" in rec

    def test_select_star_recommendation(self):
        """Recomendación para SELECT *."""
        rec = RecommendationEngine.select_star()
        assert "SELECT *" in rec or "columnas" in rec

    def test_sort_without_index_recommendation(self):
        """Recomendación para sort sin índice."""
        rec = RecommendationEngine.sort_without_index("products", "price")
        assert "products" in rec
        assert "price" in rec


class TestAntiPatternDetector:
    """Tests para AntiPatternDetector."""

    def test_initialization_default_config(self):
        """Detector se inicializa con configuración por defecto."""
        detector = AntiPatternDetector()
        assert detector.config.seq_scan_row_threshold == 10_000
        assert detector.config.row_divergence_threshold == 0.5
        assert detector.config.nested_loop_threshold == 10_000

    def test_initialization_custom_config(self):
        """Detector acepta configuración personalizada."""
        config = DetectorConfig(seq_scan_row_threshold=5000)
        detector = AntiPatternDetector(config)
        assert detector.config.seq_scan_row_threshold == 5000

    def test_empty_plan_returns_zero_patterns(self):
        """Plan vacío no detecta anti-patrones."""
        detector = AntiPatternDetector()
        result = detector.analyze({})
        assert result.score == 100
        assert len(result.anti_patterns) == 0
        assert len(result.recommendations) == 0

    def test_full_table_scan_detection(self):
        """Detecta Seq Scan en tabla grande."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Seq Scan",
            "table_name": "customers",
            "actual_rows": 50000,
            "estimated_rows": 50000,  # Same estimation, no divergence
            "children": [],
        }

        result = detector.analyze(plan)

        assert result.score == 75  # 100 - 25 (HIGH)
        assert len(result.anti_patterns) == 1
        assert result.anti_patterns[0].name == "full_table_scan"
        assert result.anti_patterns[0].severity == Severity.HIGH
        assert "customers" in result.anti_patterns[0].description
        assert len(result.recommendations) == 1

    def test_full_table_scan_ignores_small_tables(self):
        """Seq Scan en tabla pequeña NO genera warning."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Seq Scan",
            "table_name": "small_table",
            "actual_rows": 100,  # < 10,000
            "estimated_rows": 100,
            "children": [],
        }

        result = detector.analyze(plan)

        assert result.score == 100  # Sin penalización
        assert len(result.anti_patterns) == 0

    def test_row_estimation_error_detection(self):
        """Detecta divergencia > 50%."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Index Scan",
            "table_name": "orders",
            "actual_rows": 45000,
            "estimated_rows": 20000,  # Divergencia = 125%
            "children": [],
        }

        result = detector.analyze(plan)

        assert result.score == 85  # 100 - 15 (row_estimation_error MEDIUM)
        patterns = [ap for ap in result.anti_patterns if ap.name == "row_estimation_error"]
        assert len(patterns) == 1
        assert patterns[0].severity == Severity.MEDIUM

    def test_row_estimation_error_ignores_low_divergence(self):
        """Divergencia < 50% NO genera warning."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Seq Scan",
            "table_name": "orders",
            "actual_rows": 21000,
            "estimated_rows": 20000,  # Divergencia = 5%
            "children": [],
        }

        result = detector.analyze(plan)

        # Solo Seq Scan si actual_rows > 10k
        assert "row_estimation_error" not in [ap.name for ap in result.anti_patterns]

    def test_nested_loop_detection(self):
        """Detecta Nested Loop costoso."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Nested Loop",
            "actual_rows": 150000,
            "children": [
                {
                    "node_type": "Seq Scan",
                    "table_name": "orders",
                    "actual_rows": 1500,
                    "children": [],
                },
                {
                    "node_type": "Index Scan",
                    "table_name": "items",
                    "actual_rows": 100,
                    "children": [],
                },
            ],
        }

        result = detector.analyze(plan)

        assert result.score == 75  # 100 - 25 (nested_loop HIGH)
        patterns = [ap for ap in result.anti_patterns if ap.name == "nested_loop_cost"]
        assert len(patterns) == 1
        assert "150,000" in patterns[0].description  # iterations
        assert "orders" in patterns[0].description
        assert "items" in patterns[0].description

    def test_result_without_limit_detection(self):
        """Detecta resultado sin LIMIT > threshold."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Seq Scan",
            "table_name": "logs",
            "actual_rows": 100000,
            "children": [],
        }

        query = "SELECT * FROM logs WHERE status = 'active'"
        result = detector.analyze(plan, query)

        patterns = [ap for ap in result.anti_patterns if ap.name == "result_without_limit"]
        assert len(patterns) == 1
        assert patterns[0].severity == Severity.MEDIUM

    def test_result_without_limit_ignores_with_limit(self):
        """Query con LIMIT NO genera warning."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Seq Scan",
            "table_name": "logs",
            "actual_rows": 100000,
            "children": [],
        }

        query = "SELECT * FROM logs LIMIT 100"
        result = detector.analyze(plan, query)

        patterns = [ap for ap in result.anti_patterns if ap.name == "result_without_limit"]
        assert len(patterns) == 0

    def test_select_star_detection(self):
        """Detecta SELECT *."""
        detector = AntiPatternDetector()

        query = "SELECT * FROM customers WHERE age > 30"
        result = detector.analyze({}, query)

        patterns = [ap for ap in result.anti_patterns if ap.name == "select_star"]
        assert len(patterns) == 1
        assert patterns[0].severity == Severity.LOW
        assert result.score == 95  # 100 - 5 (LOW)

    def test_select_star_ignores_specific_columns(self):
        """SELECT con columnas específicas NO genera warning."""
        detector = AntiPatternDetector()

        query = "SELECT id, name, email FROM customers"
        result = detector.analyze({}, query)

        patterns = [ap for ap in result.anti_patterns if ap.name == "select_star"]
        assert len(patterns) == 0

    def test_function_in_where_detection(self):
        """Detecta función en WHERE sin índice."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Seq Scan",
            "table_name": "users",
            "actual_rows": 50000,
            "filter_condition": "LOWER(email) = 'john@example.com'",
            "index_used": None,  # Sin índice
            "children": [],
        }

        result = detector.analyze(plan)

        patterns = [ap for ap in result.anti_patterns if ap.name == "function_in_where"]
        assert len(patterns) == 1
        assert "LOWER" in patterns[0].description

    def test_sort_without_index_detection(self):
        """Detecta ORDER BY sin índice."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Sort",
            "table_name": "products",
            "actual_rows": 10000,
            "index_used": None,  # Sin índice
            "children": [],
        }

        result = detector.analyze(plan)

        patterns = [ap for ap in result.anti_patterns if ap.name == "sort_without_index"]
        assert len(patterns) == 1
        assert patterns[0].severity == Severity.MEDIUM

    def test_extract_all_nodes_recursive(self):
        """Extrae recursivamente todos los nodos."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Root",
            "children": [
                {
                    "node_type": "Nested Loop",
                    "children": [{"node_type": "Seq Scan"}, {"node_type": "Index Scan"}],
                }
            ],
        }

        nodes = detector._extract_all_nodes(plan)

        # Root + Nested Loop + Seq Scan + Index Scan = 4
        assert len(nodes) == 4
        assert nodes[0]["node_type"] == "Root"

    def test_extract_functions_from_condition(self):
        """Extrae funciones de condición WHERE."""
        detector = AntiPatternDetector()

        # Test con múltiples funciones
        funcs = detector._extract_condition_functions(
            "LOWER(email) = 'john' AND DATE(created) > '2020-01-01'"
        )

        assert "LOWER" in funcs
        assert "DATE" in funcs
        assert len(funcs) == 2

    def test_extract_functions_from_condition_no_functions(self):
        """Retorna lista vacía si no hay funciones."""
        detector = AntiPatternDetector()

        funcs = detector._extract_condition_functions("age > 30 AND status = 'active'")

        assert len(funcs) == 0

    def test_detection_result_reproducibility(self):
        """Mismo plan = mismo resultado."""
        plan = {
            "node_type": "Seq Scan",
            "table_name": "customers",
            "actual_rows": 50000,
            "estimated_rows": 20000,
            "children": [],
        }

        detector1 = AntiPatternDetector()
        result1 = detector1.analyze(plan)

        detector2 = AntiPatternDetector()
        result2 = detector2.analyze(plan)

        assert result1.score == result2.score
        assert len(result1.anti_patterns) == len(result2.anti_patterns)

    def test_multiple_anti_patterns_in_one_plan(self):
        """Un plan puede contener múltiples anti-patrones."""
        detector = AntiPatternDetector()

        plan = {
            "node_type": "Seq Scan",
            "table_name": "customers",
            "actual_rows": 50000,
            "estimated_rows": 10000,  # Divergencia 80%
            "filter_condition": "LOWER(email) = 'test'",
            "index_used": None,
            "children": [],
        }

        query = "SELECT * FROM customers WHERE LOWER(email) = 'test'"
        result = detector.analyze(plan, query)

        # Debe detectar: full_table_scan, row_estimation_error,
        # function_in_where, select_star
        assert len(result.anti_patterns) >= 3
        assert result.score < 100
