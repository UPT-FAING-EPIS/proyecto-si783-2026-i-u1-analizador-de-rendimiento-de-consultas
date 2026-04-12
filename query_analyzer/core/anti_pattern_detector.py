"""AntiPatternDetector - Detector agnóstico de anti-patrones en planes de consultas.

Este módulo proporciona detección de anti-patrones comunes en planes de ejecución
de bases de datos SQL. Es independiente del motor (PostgreSQL, MySQL, SQLite, etc.)
ya que trabaja con planes normalizados.

Componentes principales:
- ScoringEngine: Calcula score 0-100 con deducción por anti-patrones
- RecommendationEngine: Genera recomendaciones específicas con nombres reales
- AntiPatternDetector: Orquesta la detección de los 7 anti-patrones
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Niveles de severidad de los anti-patrones."""

    HIGH = "Alta"
    MEDIUM = "Media"
    LOW = "Baja"


@dataclass
class DetectorConfig:
    """Configuración personalizable del detector de anti-patrones."""

    # Umbrales de detección
    seq_scan_row_threshold: int = 10_000
    """Número mínimo de filas para alertar sobre Seq Scan sin índice"""

    row_divergence_threshold: float = 0.5
    """Divergencia máxima permitida: |actual - estimated| / estimated"""

    nested_loop_threshold: int = 10_000
    """Número máximo de iteraciones permitidas en Nested Loop"""

    max_result_rows: int = 10_000
    """Número máximo de filas sin LIMIT antes de alertar"""


@dataclass
class AntiPattern:
    """Representa un anti-patrón detectado en el plan de ejecución."""

    name: str
    """Identificador del anti-patrón: full_table_scan, row_estimation_error, etc."""

    severity: Severity
    """Nivel de severidad: Alta, Media, Baja"""

    description: str
    """Descripción clara del problema encontrado"""

    affected_table: str | None = None
    """Nombre de la tabla afectada (si aplica)"""

    affected_column: str | None = None
    """Nombre de la columna afectada (si aplica)"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Información adicional específica del anti-patrón"""


@dataclass
class DetectionResult:
    """Resultado del análisis de anti-patrones."""

    score: int
    """Score final 0-100"""

    anti_patterns: list[AntiPattern]
    """Lista de anti-patrones detectados"""

    recommendations: list[str]
    """Lista de recomendaciones generadas"""


class ScoringEngine:
    """Motor de puntuación 0-100.

    Cada anti-patrón detectado descuenta puntos según su severidad.
    El score final nunca puede ser negativo (mínimo 0).

    Escala de penalización:
    - Severidad ALTA: -25 puntos (máximo)
    - Severidad MEDIA: -15 puntos (máximo)
    - Severidad BAJA: -5 puntos (máximo)
    """

    # Penalización máxima por severidad
    PENALTIES = {
        Severity.HIGH: 25,
        Severity.MEDIUM: 15,
        Severity.LOW: 5,
    }

    def __init__(self, base_score: int = 100):
        """Inicializa el motor de puntuación.

        Args:
            base_score: Puntuación inicial (por defecto 100)
        """
        self.base_score = base_score
        self.current_score = base_score
        self.deductions: list[tuple[str, Severity, int]] = []

    def deduct(self, anti_pattern_name: str, severity: Severity, amount: int | None = None) -> None:
        """Descuenta puntos por un anti-patrón detectado.

        Args:
            anti_pattern_name: Nombre del anti-patrón
            severity: Nivel de severidad
            amount: Cantidad a descontar (si None, usa el valor por defecto por severidad)
        """
        if amount is None:
            amount = self.PENALTIES.get(severity, 0)

        self.current_score -= amount
        self.deductions.append((anti_pattern_name, severity, amount))

    def get_score(self) -> int:
        """Obtiene el score final 0-100 (garantizado no negativo).

        Returns:
            Score final entre 0 y 100
        """
        return max(0, min(100, self.current_score))

    def reset(self) -> None:
        """Resetea el scoring engine a su estado inicial."""
        self.current_score = self.base_score
        self.deductions.clear()


class RecommendationEngine:
    """Generador de recomendaciones específicas para cada anti-patrón.

    Las recomendaciones incluyen nombres reales de tablas, columnas y
    valores específicos extraídos del análisis.
    """

    @staticmethod
    def full_table_scan(
        table_name: str, row_count: int, filter_condition: str | None = None
    ) -> str:
        """Recomendación para Seq Scan sin índice.

        Args:
            table_name: Nombre de la tabla
            row_count: Número de filas en la tabla
            filter_condition: Condición del WHERE (ej: "age > 30")

        Returns:
            Texto de recomendación
        """
        rec = f"Crear índice en tabla '{table_name}' ({row_count:,} filas). "

        if filter_condition:
            rec += f"Analizar la cláusula WHERE '{filter_condition}' "
            rec += "para identificar columnas candidatas."
        else:
            rec += "Analizar la cláusula WHERE para identificar columnas candidatas."

        return rec

    @staticmethod
    def row_estimation_error(
        table_name: str, actual: int, estimated: int, divergence_pct: float
    ) -> str:
        """Recomendación para error de estimación de filas.

        Args:
            table_name: Nombre de la tabla
            actual: Filas reales encontradas
            estimated: Filas estimadas por el plan
            divergence_pct: Porcentaje de divergencia

        Returns:
            Texto de recomendación
        """
        return (
            f"Ejecutar ANALYZE en tabla '{table_name}' para actualizar estadísticas. "
            f"Divergencia: {actual:,} (actual) vs {estimated:,} (estimado) = {divergence_pct:.1f}%"
        )

    @staticmethod
    def nested_loop_cost(
        iterations: int, table1: str | None = None, table2: str | None = None
    ) -> str:
        """Recomendación para Nested Loop costoso.

        Args:
            iterations: Número de iteraciones del nested loop
            table1: Nombre de la tabla exterior (opcional)
            table2: Nombre de la tabla interior (opcional)

        Returns:
            Texto de recomendación
        """
        rec = (
            f"Evaluar Hash Join o Sort-Merge Join en lugar de Nested Loop "
            f"({iterations:,} iteraciones). "
        )

        if table1 and table2:
            rec += f"Revisar índices en '{table1}' y '{table2}'."
        else:
            rec += "Revisar índices en las tablas involucradas."

        return rec

    @staticmethod
    def result_without_limit(table_name: str, row_count: int) -> str:
        """Recomendación para resultado sin LIMIT.

        Args:
            table_name: Nombre de la tabla
            row_count: Número de filas retornadas

        Returns:
            Texto de recomendación
        """
        return (
            f"Agregar LIMIT a la consulta o implementar paginación. "
            f"Query retorna {row_count:,} filas de tabla '{table_name}'."
        )

    @staticmethod
    def function_in_where(
        function_name: str, column_name: str, table_name: str | None = None
    ) -> str:
        """Recomendación para función en WHERE sobre columna indexada.

        Args:
            function_name: Nombre de la función (ej: "LOWER", "DATE")
            column_name: Nombre de la columna
            table_name: Nombre de la tabla (opcional)

        Returns:
            Texto de recomendación
        """
        rec = (
            f"Reescribir condición WHERE sin función o usar índice funcional. "
            f"Función '{function_name}' aplicada a columna '{column_name}' "
        )

        if table_name:
            rec += f"en tabla '{table_name}'."
        else:
            rec += "impide uso de índice."

        return rec

    @staticmethod
    def select_star(table_count: int = 1) -> str:
        """Recomendación para SELECT *.

        Args:
            table_count: Número de tablas en la query

        Returns:
            Texto de recomendación
        """
        return (
            "Seleccionar solo columnas necesarias en lugar de SELECT *. "
            "Reduce transferencia de datos y mejora el caché."
        )

    @staticmethod
    def sort_without_index(table_name: str, sort_column: str | None = None) -> str:
        """Recomendación para ORDER BY sin índice (filesort).

        Args:
            table_name: Nombre de la tabla
            sort_column: Nombre de la columna de ordenamiento (opcional)

        Returns:
            Texto de recomendación
        """
        rec = f"Crear índice en tabla '{table_name}' para ORDER BY"

        if sort_column:
            rec += f" sobre columna '{sort_column}'."
        else:
            rec += "."

        return rec


class AntiPatternDetector:
    """Detector agnóstico de anti-patrones en planes de ejecución.

    Analiza planes normalizados (independientes del motor SQL) e identifica
    los siguientes anti-patrones:
    1. Full table scan (Seq Scan sin índice)
    2. Row estimation error (divergencia > 50%)
    3. Nested loop costoso (> 10k iteraciones)
    4. Resultado sin LIMIT (> 10k filas)
    5. Función en WHERE (sobre columna indexada)
    6. SELECT * (columnas innecesarias)
    7. Sort sin índice (filesort/Using filesort)
    """

    def __init__(self, config: DetectorConfig | None = None):
        """Inicializa el detector con configuración opcional.

        Args:
            config: Configuración personalizada (usa defaults si None)
        """
        self.config = config or DetectorConfig()
        self.scoring_engine = ScoringEngine()

    def analyze(self, plan: dict[str, Any], query: str = "") -> DetectionResult:
        """Analiza un plan normalizado y detecta anti-patrones.

        Args:
            plan: Plan de ejecución normalizado
            query: Query SQL original (para detecciones que lo requieren)

        Returns:
            DetectionResult con score, anti-patrones y recomendaciones
        """
        # Reset scoring para nuevo análisis
        self.scoring_engine = ScoringEngine()

        anti_patterns: list[AntiPattern] = []

        # Ejecuta todos los detectores
        anti_patterns.extend(self._detect_full_table_scan(plan))
        anti_patterns.extend(self._detect_row_estimation_error(plan))
        anti_patterns.extend(self._detect_nested_loop_cost(plan))
        anti_patterns.extend(self._detect_result_without_limit(plan, query))
        anti_patterns.extend(self._detect_function_in_where(plan))
        anti_patterns.extend(self._detect_select_star(query))
        anti_patterns.extend(self._detect_sort_without_index(plan))

        # Genera recomendaciones específicas
        recommendations = self._generate_recommendations(anti_patterns)

        return DetectionResult(
            score=self.scoring_engine.get_score(),
            anti_patterns=anti_patterns,
            recommendations=recommendations,
        )

    def _detect_full_table_scan(self, plan: dict[str, Any]) -> list[AntiPattern]:
        """Detecta Seq Scan sin índice en tablas > threshold de filas.

        Condición: node_type == "Seq Scan" y actual_rows > threshold
        Severidad: ALTA
        """
        patterns: list[AntiPattern] = []

        for node in self._extract_all_nodes(plan):
            node_type = node.get("node_type", "").strip()

            # Detecta Seq Scan (PostgreSQL)
            if node_type == "Seq Scan":
                actual_rows = node.get("actual_rows", 0)
                table_name = node.get("table_name", "unknown")

                if actual_rows > self.config.seq_scan_row_threshold:
                    pattern = AntiPattern(
                        name="full_table_scan",
                        severity=Severity.HIGH,
                        description=(
                            f"Seq Scan sin índice en tabla '{table_name}' ({actual_rows:,} filas)"
                        ),
                        affected_table=table_name,
                        affected_column=None,
                        metadata={
                            "rows": actual_rows,
                            "node_type": node_type,
                            "filter_condition": node.get("filter_condition"),
                        },
                    )
                    patterns.append(pattern)
                    self.scoring_engine.deduct("full_table_scan", Severity.HIGH)

        return patterns

    def _detect_row_estimation_error(self, plan: dict[str, Any]) -> list[AntiPattern]:
        """Detecta divergencia entre filas reales y estimadas > 50%.

        Condición: |actual - estimated| / estimated > 0.5
        Severidad: MEDIA
        """
        patterns: list[AntiPattern] = []

        for node in self._extract_all_nodes(plan):
            actual = node.get("actual_rows")
            estimated = node.get("estimated_rows")
            table_name = node.get("table_name", "unknown")

            if actual is not None and estimated is not None and estimated > 0:
                divergence = abs(actual - estimated) / estimated

                if divergence > self.config.row_divergence_threshold:
                    divergence_pct = divergence * 100

                    pattern = AntiPattern(
                        name="row_estimation_error",
                        severity=Severity.MEDIUM,
                        description=(
                            f"Divergencia en estimación en tabla '{table_name}': "
                            f"{actual:,} (actual) vs {estimated:,} (estimado) = {divergence_pct:.1f}%"
                        ),
                        affected_table=table_name,
                        affected_column=None,
                        metadata={
                            "actual": actual,
                            "estimated": estimated,
                            "divergence": divergence,
                            "divergence_pct": divergence_pct,
                        },
                    )
                    patterns.append(pattern)
                    self.scoring_engine.deduct("row_estimation_error", Severity.MEDIUM)

        return patterns

    def _detect_nested_loop_cost(self, plan: dict[str, Any]) -> list[AntiPattern]:
        """Detecta Nested Loop con > threshold iteraciones.

        Condición: node_type == "Nested Loop" y outer_rows * inner_rows > threshold
        Severidad: ALTA
        """
        patterns: list[AntiPattern] = []

        for node in self._extract_all_nodes(plan):
            if node.get("node_type") == "Nested Loop":
                children = node.get("children", [])

                if len(children) >= 2:
                    outer_rows = children[0].get("actual_rows", 0)
                    inner_rows = children[1].get("actual_rows", 0)

                    if outer_rows and inner_rows:
                        iterations = outer_rows * inner_rows

                        if iterations > self.config.nested_loop_threshold:
                            outer_table = children[0].get("table_name", "unknown")
                            inner_table = children[1].get("table_name", "unknown")

                            pattern = AntiPattern(
                                name="nested_loop_cost",
                                severity=Severity.HIGH,
                                description=(
                                    f"Nested Loop costoso: {iterations:,} iteraciones "
                                    f"('{outer_table}' × '{inner_table}')"
                                ),
                                affected_table=outer_table,
                                affected_column=None,
                                metadata={
                                    "iterations": iterations,
                                    "outer_table": outer_table,
                                    "inner_table": inner_table,
                                    "outer_rows": outer_rows,
                                    "inner_rows": inner_rows,
                                },
                            )
                            patterns.append(pattern)
                            self.scoring_engine.deduct("nested_loop_cost", Severity.HIGH)

        return patterns

    def _detect_result_without_limit(self, plan: dict[str, Any], query: str) -> list[AntiPattern]:
        """Detecta resultado sin LIMIT en tabla > max_result_rows filas.

        Condición: actual_rows > max_result_rows y query sin LIMIT
        Severidad: MEDIA
        """
        patterns: list[AntiPattern] = []

        # Obtiene filas del nodo raíz
        actual_rows = plan.get("actual_rows", 0)
        table_name = plan.get("table_name", "unknown")

        if actual_rows > self.config.max_result_rows:
            # Verifica que query NO tenga LIMIT
            has_limit = bool(re.search(r"\bLIMIT\b", query, re.IGNORECASE))

            if not has_limit and query:  # Solo si hay query disponible
                pattern = AntiPattern(
                    name="result_without_limit",
                    severity=Severity.MEDIUM,
                    description=(
                        f"Query retorna {actual_rows:,} filas sin LIMIT. "
                        f"Potencial problema de rendimiento y memoria."
                    ),
                    affected_table=table_name,
                    affected_column=None,
                    metadata={"rows": actual_rows},
                )
                patterns.append(pattern)
                self.scoring_engine.deduct("result_without_limit", Severity.MEDIUM)

        return patterns

    def _detect_function_in_where(self, plan: dict[str, Any]) -> list[AntiPattern]:
        """Detecta funciones aplicadas a columnas en WHERE.

        Condición: filter_condition contiene función y no hay index_used
        Severidad: ALTA
        """
        patterns: list[AntiPattern] = []

        for node in self._extract_all_nodes(plan):
            filter_condition = node.get("filter_condition", "")
            has_index = bool(node.get("index_used"))
            table_name = node.get("table_name", "unknown")

            if filter_condition and not has_index:
                functions = self._extract_condition_functions(filter_condition)

                for func_name in functions:
                    pattern = AntiPattern(
                        name="function_in_where",
                        severity=Severity.HIGH,
                        description=(
                            f"Función '{func_name}' aplicada en WHERE sobre "
                            f"columna en tabla '{table_name}'. Índice no se utiliza."
                        ),
                        affected_table=table_name,
                        affected_column=None,
                        metadata={"function": func_name, "filter_condition": filter_condition},
                    )
                    patterns.append(pattern)
                    self.scoring_engine.deduct("function_in_where", Severity.HIGH)

        return patterns

    def _detect_select_star(self, query: str) -> list[AntiPattern]:
        """Detecta SELECT * en la query.

        Condición: Query contiene "SELECT *"
        Severidad: BAJA
        """
        patterns: list[AntiPattern] = []

        if query and re.search(r"SELECT\s+\*\s", query, re.IGNORECASE):
            pattern = AntiPattern(
                name="select_star",
                severity=Severity.LOW,
                description=(
                    "SELECT * carga todas las columnas innecesariamente. "
                    "Aumenta transferencia de datos e impacta caché."
                ),
                affected_table=None,
                affected_column=None,
                metadata={},
            )
            patterns.append(pattern)
            self.scoring_engine.deduct("select_star", Severity.LOW)

        return patterns

    def _detect_sort_without_index(self, plan: dict[str, Any]) -> list[AntiPattern]:
        """Detecta ORDER BY sin índice (filesort/Sort node).

        Condición: node_type == "Sort" sin index_used
                  O "Using filesort" en extra_info
        Severidad: MEDIA
        """
        patterns: list[AntiPattern] = []

        for node in self._extract_all_nodes(plan):
            is_sort_node = node.get("node_type") == "Sort"
            has_filesort = "Using filesort" in node.get("extra_info", [])
            has_index = bool(node.get("index_used"))
            table_name = node.get("table_name", "unknown")

            if (is_sort_node or has_filesort) and not has_index:
                pattern = AntiPattern(
                    name="sort_without_index",
                    severity=Severity.MEDIUM,
                    description=(
                        f"ORDER BY sin índice en tabla '{table_name}'. Utiliza filesort (caro)."
                    ),
                    affected_table=table_name,
                    affected_column=None,
                    metadata={"is_sort_node": is_sort_node, "has_filesort": has_filesort},
                )
                patterns.append(pattern)
                self.scoring_engine.deduct("sort_without_index", Severity.MEDIUM)

        return patterns

    def _extract_all_nodes(
        self, plan: dict[str, Any], nodes: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """Extrae recursivamente todos los nodos del plan.

        Args:
            plan: Plan de ejecución (o nodo actual)
            nodes: Lista acumulativa de nodos (uso interno)

        Returns:
            Lista de todos los nodos del plan
        """
        if nodes is None:
            nodes = []

        if plan:
            nodes.append(plan)

            # Recursión en nodos hijos
            for child in plan.get("children", []):
                self._extract_all_nodes(child, nodes)

        return nodes

    def _extract_condition_functions(self, condition: str) -> list[str]:
        """Extrae nombres de funciones en una condición WHERE.

        Ejemplos:
            "LOWER(name) = 'john'" -> ["LOWER"]
            "DATE(created_at) > '2020-01-01'" -> ["DATE"]
            "age > 30" -> []

        Args:
            condition: Condición del WHERE

        Returns:
            Lista de nombres de funciones encontradas
        """
        if not condition:
            return []

        # Patrón: nombre_función(...)
        # Busca word boundary, luego palabra, luego (
        pattern = r"\b([A-Z_][A-Z0-9_]*)\s*\("
        matches = re.findall(pattern, condition, re.IGNORECASE)

        return list(set(matches))  # Deduplica

    def _generate_recommendations(self, anti_patterns: list[AntiPattern]) -> list[str]:
        """Genera recomendaciones específicas basadas en anti-patrones detectados.

        Args:
            anti_patterns: Lista de anti-patrones detectados

        Returns:
            Lista de recomendaciones de texto
        """
        recommendations: list[str] = []

        for ap in anti_patterns:
            rec = None

            if ap.name == "full_table_scan":
                rec = RecommendationEngine.full_table_scan(
                    ap.affected_table or "unknown",
                    ap.metadata.get("rows", 0),
                    ap.metadata.get("filter_condition"),
                )

            elif ap.name == "row_estimation_error":
                rec = RecommendationEngine.row_estimation_error(
                    ap.affected_table or "unknown",
                    ap.metadata.get("actual", 0),
                    ap.metadata.get("estimated", 0),
                    ap.metadata.get("divergence_pct", 0.0),
                )

            elif ap.name == "nested_loop_cost":
                rec = RecommendationEngine.nested_loop_cost(
                    ap.metadata.get("iterations", 0),
                    ap.metadata.get("outer_table"),
                    ap.metadata.get("inner_table"),
                )

            elif ap.name == "result_without_limit":
                rec = RecommendationEngine.result_without_limit(
                    ap.affected_table or "unknown", ap.metadata.get("rows", 0)
                )

            elif ap.name == "function_in_where":
                rec = RecommendationEngine.function_in_where(
                    ap.metadata.get("function", "unknown"), "columna", ap.affected_table
                )

            elif ap.name == "select_star":
                rec = RecommendationEngine.select_star()

            elif ap.name == "sort_without_index":
                rec = RecommendationEngine.sort_without_index(ap.affected_table or "unknown")

            if rec and rec not in recommendations:
                recommendations.append(rec)

        return recommendations


class MongoDBAntiPatternDetector:
    """Detect MongoDB-specific anti-patterns."""

    PATTERNS = [
        "collection_scan",
        "high_doc_examination_ratio",
        "sort_without_index",
        "regex_without_prefix",
    ]

    @staticmethod
    def detect(parsed_explain: dict) -> dict:
        """Detect anti-patterns in MongoDB query.

        Args:
            parsed_explain: Output from MongoExplainParser.parse()

        Returns:
            Detection results with anti-patterns and final score
            {
                "anti_patterns": [...],
                "total_penalty": int,
                "final_score": float (0-100)
            }
        """
        anti_patterns: list[dict[str, Any]] = []
        total_penalty = 0

        metrics = parsed_explain["metrics"]

        if parsed_explain["has_collection_scan"]:
            pattern = {
                "name": "collection_scan",
                "severity": "HIGH",
                "score_penalty": -25,
                "description": "Query performs full collection scan (COLLSCAN)",
                "recommendation": "Create an index on the queried fields",
            }
            anti_patterns.append(pattern)
            total_penalty += -25

        docs_returned = metrics["documents_returned"]
        docs_examined = metrics["documents_examined"]

        if docs_returned > 0 and docs_examined > 0:
            ratio = docs_examined / docs_returned
            if ratio > 10:
                pattern = {
                    "name": "high_doc_examination_ratio",
                    "severity": "MEDIUM",
                    "score_penalty": -15,
                    "description": (
                        f"Query examined {docs_examined} documents to return "
                        f"{docs_returned} ({ratio:.1f}x ratio)"
                    ),
                    "recommendation": "Create a more selective index",
                }
                anti_patterns.append(pattern)
                total_penalty += -15

        if parsed_explain["has_sort"] and not parsed_explain["has_index"]:
            pattern = {
                "name": "sort_without_index",
                "severity": "MEDIUM",
                "score_penalty": -15,
                "description": "Sorting performed in memory (no index support)",
                "recommendation": "Create index on sort field(s)",
            }
            anti_patterns.append(pattern)
            total_penalty += -15

        final_score = max(0, 100 + total_penalty)

        return {
            "anti_patterns": anti_patterns,
            "total_penalty": total_penalty,
            "final_score": final_score,
        }
