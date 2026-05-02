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
    def order_by_rand() -> str:
        """Recomendación para ORDER BY RAND()."""
        return (
            "Evitar usar ORDER BY RAND() o similar. Esta operación fuerza a "
            "la base de datos a asignar un valor aleatorio a cada fila y ordenar toda "
            "la tabla, lo cual es extremadamente ineficiente."
        )

    @staticmethod
    def leading_wildcard(pattern: str) -> str:
        """Recomendación para comodín inicial en LIKE."""
        return (
            f"El patrón '{pattern}' comienza con un comodín (%). "
            "Esto desactiva los índices B-Tree y fuerza un escaneo completo de la tabla. "
            "Considerar usar índices Full-Text o rediseñar la búsqueda."
        )

    @staticmethod
    def or_multiple_columns() -> str:
        """Recomendación para OR en múltiples columnas."""
        return (
            "Dividir la consulta en dos partes utilizando UNION o UNION ALL "
            "(si no hay duplicados) para que cada subconsulta aproveche los índices correspondientes."
        )

    @staticmethod
    def unfiltered_aggregation() -> str:
        """Recomendación para GROUP BY sin WHERE o LIMIT."""
        return (
            "Agregar filtros de fecha o paginación (LIMIT / OFFSET) si el "
            "objetivo es obtener análisis recientes o por lotes."
        )

    @staticmethod
    def union_without_all() -> str:
        """Recomendación para UNION sin ALL."""
        return (
            "Reemplazar UNION por UNION ALL si no es estrictamente necesario eliminar "
            "duplicados. UNION requiere que la base de datos ordene y desduplique todo "
            "el conjunto de resultados, lo cual consume mucha memoria y CPU."
        )

    @staticmethod
    def negative_condition(operator: str) -> str:
        """Recomendación para condiciones negativas en WHERE."""
        return (
            f"Se detectó el operador negativo '{operator}' en la cláusula WHERE. "
            "Las condiciones negativas generalmente impiden el uso de índices B-Tree "
            "y fuerzan un escaneo completo de tabla. Considerar usar lógica positiva "
            "(ej. IN) si es posible."
        )

    @staticmethod
    def subquery_in_select() -> str:
        """Recomendación para subconsultas en SELECT."""
        return (
            "Mover la subconsulta del SELECT a un LEFT JOIN con GROUP BY. "
            "Una subconsulta en la cláusula SELECT obliga al motor a ejecutarla "
            "por cada fila retornada (Problema N+1), degradando el rendimiento."
        )

    @staticmethod
    def cartesian_product() -> str:
        """Recomendación para Producto Cartesiano."""
        return (
            "Se detectó un Producto Cartesiano (Cross Join implícito). "
            "Esto ocurre al listar múltiples tablas sin una condición de unión. "
            "Usar la sintaxis explícita INNER JOIN ... ON para evitar resultados duplicados masivos."
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

    @staticmethod
    def mongodb_collection_scan(collection_name: str, docs_examined: int) -> str:
        """Recomendación para collection scan en MongoDB.

        Args:
            collection_name: Nombre de la colección
            docs_examined: Número de documentos examinados

        Returns:
            Texto de recomendación
        """
        return (
            f"Crear índice en campos consultados de la colección '{collection_name}' "
            f"({docs_examined:,} documentos examinados). Analizar las condiciones de filtro "
            f"para identificar campos candidatos a indexar."
        )

    @staticmethod
    def mongodb_high_doc_ratio(collection_name: str, ratio: float, docs_examined: int) -> str:
        """Recomendación para alto ratio de examinación de documentos.

        Args:
            collection_name: Nombre de la colección
            ratio: Ratio de docs_examined / docs_returned
            docs_examined: Número de documentos examinados

        Returns:
            Texto de recomendación
        """
        return (
            f"Crear índice más selectivo en colección '{collection_name}'. "
            f"Query examinó {ratio:.1f}x más documentos ({docs_examined:,}) de los que retornó. "
            f"Considerar índice compuesto en campos de filtro + sort."
        )

    @staticmethod
    def mongodb_sort_without_index(collection_name: str, sort_field: str | None = None) -> str:
        """Recomendación para sort en memoria.

        Args:
            collection_name: Nombre de la colección
            sort_field: Campo de ordenamiento (si aplica)

        Returns:
            Texto de recomendación
        """
        rec = f"Crear índice para evitar sort en memoria en colección '{collection_name}'. "

        if sort_field:
            rec += f"Indexar campo '{sort_field}' para ORDER BY. "
        else:
            rec += "Indexar campos de ordenamiento. "

        rec += "Considerar índice compuesto si se combina con filtros."

        return rec

    @staticmethod
    def mongodb_regex_without_prefix(field_name: str, pattern: str | None = None) -> str:
        """Recomendación para regex sin anclaje.

        Args:
            field_name: Nombre del campo con regex
            pattern: Patrón regex (si aplica)

        Returns:
            Texto de recomendación
        """
        rec = (
            f"Usar regex anclado (ej: /^prefix/) en campo '{field_name}' para aprovechar índices. "
        )
        rec += "Patrones sin anclaje requieren full collection scan."

        if pattern:
            rec += f" Patrón actual: {pattern}"

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
    8. ORDER BY RAND() (ordenamiento aleatorio costoso)
    9. Comodín inicial en LIKE (desactiva índices B-Tree)
    10. Uso de OR con múltiples columnas (descarte de índices combinados)
    11. Agregación sin filtrado (GROUP BY masivo sin WHERE)
    12. Uso de UNION sin ALL (ordenamiento y desduplicación costosa)
    13. Condiciones negativas en WHERE (desactiva índices)
    14. Subconsultas en SELECT (Problema de N+1)
    15. Producto Cartesiano (Consulta sin condiciones de unión)
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
        anti_patterns.extend(self._detect_order_by_rand(query))
        anti_patterns.extend(self._detect_leading_wildcard(query))
        anti_patterns.extend(self._detect_or_multiple_columns(query))
        anti_patterns.extend(self._detect_unfiltered_aggregation(query))
        anti_patterns.extend(self._detect_union_without_all(query))
        anti_patterns.extend(self._detect_negative_condition(query))
        anti_patterns.extend(self._detect_subquery_in_select(query))
        anti_patterns.extend(self._detect_cartesian_product(query))
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
                actual_rows = node.get("actual_rows") or 0
                table_name = node.get("table_name", "unknown")

                if actual_rows >= self.config.seq_scan_row_threshold:
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
        actual_rows = plan.get("actual_rows") or 0
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

    def _detect_order_by_rand(self, query: str) -> list[AntiPattern]:
        """Detecta ORDER BY RAND() o similares en la query.
        
        Severidad: ALTA
        """
        patterns: list[AntiPattern] = []

        if query and re.search(r"ORDER\s+BY\s+(RAND|RANDOM)\s*\(", query, re.IGNORECASE):
            pattern = AntiPattern(
                name="order_by_rand",
                severity=Severity.HIGH,
                description=(
                    "Se detectó ORDER BY RAND(). Esto requiere escanear toda la tabla "
                    "y crear una tabla temporal para ordenamiento, destruyendo el rendimiento."
                ),
                affected_table=None,
                affected_column=None,
                metadata={},
            )
            patterns.append(pattern)
            self.scoring_engine.deduct("order_by_rand", Severity.HIGH)

        return patterns

    def _detect_leading_wildcard(self, query: str) -> list[AntiPattern]:
        """Detecta LIKE '%...' en la query.
        
        Severidad: ALTA
        """
        patterns: list[AntiPattern] = []

        if query:
            matches = re.findall(r"LIKE\s+['\"](%[^'\"]+)['\"]", query, re.IGNORECASE)
            for match in matches:
                pattern = AntiPattern(
                    name="leading_wildcard",
                    severity=Severity.HIGH,
                    description=(
                        f"Se detectó un comodín inicial en LIKE '{match}'. "
                        "Esto impide el uso de índices y fuerza un escaneo completo."
                    ),
                    affected_table=None,
                    affected_column=None,
                    metadata={"pattern": match},
                )
                patterns.append(pattern)
                self.scoring_engine.deduct("leading_wildcard", Severity.HIGH)

        return patterns

    def _detect_or_multiple_columns(self, query: str) -> list[AntiPattern]:
        """Detecta el uso de OR con columnas diferentes en el WHERE.
        
        Severidad: MEDIA
        """
        patterns: list[AntiPattern] = []

        if query:
            where_match = re.search(r"WHERE\s+(.*?)(?:GROUP\s+BY|ORDER\s+BY|LIMIT|$)", query, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1)
                or_matches = re.findall(r"([a-zA-Z0-9_.]+)\s*(?:=|>|<|>=|<=|LIKE|IN)[\s\S]+?\bOR\b\s+([a-zA-Z0-9_.]+)\s*(?:=|>|<|>=|<=|LIKE|IN)", where_clause, re.IGNORECASE)
                
                detected = False
                for col1, col2 in or_matches:
                    if col1.strip().lower() != col2.strip().lower():
                        detected = True
                        break
                
                if detected:
                    pattern = AntiPattern(
                        name="or_multiple_columns",
                        severity=Severity.MEDIUM,
                        description=(
                            "El uso del operador OR sobre columnas diferentes puede provocar que "
                            "el optimizador de consultas descarte el índice y opte por escanear toda la tabla."
                        ),
                        affected_table=None,
                        affected_column=None,
                        metadata={},
                    )
                    patterns.append(pattern)
                    self.scoring_engine.deduct("or_multiple_columns", Severity.MEDIUM)

        return patterns

    def _detect_unfiltered_aggregation(self, query: str) -> list[AntiPattern]:
        """Detecta el uso de GROUP BY sin WHERE ni LIMIT en tablas grandes.
        
        Severidad: MEDIA
        """
        patterns: list[AntiPattern] = []

        if query:
            has_group_by = bool(re.search(r"\bGROUP\s+BY\b", query, re.IGNORECASE))
            has_where = bool(re.search(r"\bWHERE\b", query, re.IGNORECASE))
            has_limit = bool(re.search(r"\bLIMIT\b", query, re.IGNORECASE))

            if has_group_by and not has_where and not has_limit:
                pattern = AntiPattern(
                    name="unfiltered_aggregation",
                    severity=Severity.MEDIUM,
                    description=(
                        "La consulta realiza un escaneo y agrupamiento de todos los registros. "
                        "Si la base de datos crece exponencialmente, esta consulta consumirá una gran "
                        "cantidad de memoria temporal para realizar el GROUP BY."
                    ),
                    affected_table=None,
                    affected_column=None,
                    metadata={},
                )
                patterns.append(pattern)
                self.scoring_engine.deduct("unfiltered_aggregation", Severity.MEDIUM)

        return patterns

    def _detect_union_without_all(self, query: str) -> list[AntiPattern]:
        """Detecta el uso de UNION sin ALL.
        
        Severidad: MEDIA
        """
        patterns: list[AntiPattern] = []
        if query and re.search(r"\bUNION\b(?!\s+ALL)", query, re.IGNORECASE):
            pattern = AntiPattern(
                name="union_without_all",
                severity=Severity.MEDIUM,
                description=(
                    "Se detectó UNION en lugar de UNION ALL. Esto introduce "
                    "un paso oculto y costoso de desduplicación de registros."
                ),
                affected_table=None,
                affected_column=None,
                metadata={},
            )
            patterns.append(pattern)
            self.scoring_engine.deduct("union_without_all", Severity.MEDIUM)
        return patterns

    def _detect_negative_condition(self, query: str) -> list[AntiPattern]:
        """Detecta operadores negativos en WHERE (!=, <>, NOT IN, NOT LIKE).
        
        Severidad: MEDIA
        """
        patterns: list[AntiPattern] = []
        if query:
            where_match = re.search(r"\bWHERE\b\s+(.*?)(?:GROUP\s+BY|ORDER\s+BY|LIMIT|$)", query, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1)
                matches = re.findall(r"(!=|<>|\bNOT\s+IN\b|\bNOT\s+LIKE\b)", where_clause, re.IGNORECASE)
                if matches:
                    operator = matches[0].strip().upper()
                    # Normalizar múltiples espacios
                    operator = re.sub(r"\s+", " ", operator)
                    pattern = AntiPattern(
                        name="negative_condition",
                        severity=Severity.MEDIUM,
                        description=(
                            f"Uso de condición negativa ('{operator}') en el WHERE. "
                            "Esto fuerza escaneos completos de tabla e ignora índices."
                        ),
                        affected_table=None,
                        affected_column=None,
                        metadata={"operator": operator},
                    )
                    patterns.append(pattern)
                    self.scoring_engine.deduct("negative_condition", Severity.MEDIUM)
        return patterns

    def _detect_subquery_in_select(self, query: str) -> list[AntiPattern]:
        """Detecta subconsultas dentro de la cláusula SELECT.
        
        Severidad: ALTA
        """
        patterns: list[AntiPattern] = []
        if query:
            select_match = re.search(r"\bSELECT\b(.*?)\bFROM\b", query, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_clause = select_match.group(1)
                if re.search(r"\(\s*SELECT\b", select_clause, re.IGNORECASE):
                    pattern = AntiPattern(
                        name="subquery_in_select",
                        severity=Severity.HIGH,
                        description=(
                            "Subconsulta detectada en la cláusula SELECT. "
                            "Se ejecutará por cada fila (Problema N+1) impactando severamente el rendimiento."
                        ),
                        affected_table=None,
                        affected_column=None,
                        metadata={},
                    )
                    patterns.append(pattern)
                    self.scoring_engine.deduct("subquery_in_select", Severity.HIGH)
        return patterns

    def _detect_cartesian_product(self, query: str) -> list[AntiPattern]:
        """Detecta productos cartesianos (múltiples tablas sin JOIN explícito ni WHERE relacional).
        
        Severidad: CRÍTICA
        """
        patterns: list[AntiPattern] = []
        if query:
            # Detectar si hay múltiples tablas separadas por coma en el FROM
            from_match = re.search(r"\bFROM\b\s+([^;]+?)(?:\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT|;|$)", query, re.IGNORECASE | re.DOTALL)
            if from_match:
                tables_part = from_match.group(1)
                tables = [t.strip() for t in tables_part.split(",") if t.strip()]
                
                # Si hay más de una tabla separada por coma...
                if len(tables) > 1:
                    # Verificar si falta un JOIN explícito o condiciones en el WHERE
                    # (Aproximación estática: si no hay JOIN y no hay condiciones de igualdad en el WHERE)
                    has_join = bool(re.search(r"\bJOIN\b", query, re.IGNORECASE))
                    has_where = bool(re.search(r"\bWHERE\b", query, re.IGNORECASE))
                    
                    if not has_join:
                        # Si no hay WHERE, es un producto cartesiano puro
                        # Si hay WHERE, verificamos si hay al menos una igualdad (muy simplificado)
                        is_cartesian = not has_where
                        if has_where:
                            where_part = query.lower().split("where")[1]
                            # Buscamos algo como tabla1.id = tabla2.id
                            is_cartesian = "=" not in where_part

                        if is_cartesian:
                            pattern = AntiPattern(
                                name="cartesian_product",
                                severity=Severity.HIGH, # Usamos HIGH porque ScoringEngine maneja HIGH como máx
                                description=(
                                    "Producto Cartesiano detectado. Consultar múltiples tablas sin "
                                    "condiciones de unión genera un volumen masivo de datos innecesarios."
                                ),
                                affected_table=None,
                                affected_column=None,
                                metadata={},
                            )
                            patterns.append(pattern)
                            # Penalización doble (Severidad Alta x 1.5 aprox = 40 puntos si ScoringEngine lo permite)
                            self.scoring_engine.deduct("cartesian_product", Severity.HIGH, amount=40)
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

            elif ap.name == "order_by_rand":
                rec = RecommendationEngine.order_by_rand()

            elif ap.name == "leading_wildcard":
                rec = RecommendationEngine.leading_wildcard(ap.metadata.get("pattern", "%"))

            elif ap.name == "or_multiple_columns":
                rec = RecommendationEngine.or_multiple_columns()

            elif ap.name == "unfiltered_aggregation":
                rec = RecommendationEngine.unfiltered_aggregation()

            elif ap.name == "union_without_all":
                rec = RecommendationEngine.union_without_all()

            elif ap.name == "negative_condition":
                rec = RecommendationEngine.negative_condition(ap.metadata.get("operator", "negativo"))

            elif ap.name == "subquery_in_select":
                rec = RecommendationEngine.subquery_in_select()

            elif ap.name == "cartesian_product":
                rec = RecommendationEngine.cartesian_product()

            if rec and rec not in recommendations:
                recommendations.append(rec)

        return recommendations

    def analyze_influxdb_patterns(
        self, normalized_plan: dict[str, Any], query: str = ""
    ) -> DetectionResult:
        """Analyze InfluxDB/Flux-specific anti-patterns.

        Detects patterns unique to InfluxDB's Flux language and time-series
        workloads that don't apply to SQL databases.

        Args:
            normalized_plan: Normalized plan with flux_metadata field
            query: Flux query string (for context)

        Returns:
            DetectionResult with InfluxDB-specific scoring (0-100)
        """
        # Reset scoring for new analysis
        self.scoring_engine = ScoringEngine()

        anti_patterns: list[AntiPattern] = []
        flux_metadata = normalized_plan.get("flux_metadata", {})

        # AP1: Unbounded Query (CRITICAL - no time filter)
        if not flux_metadata.get("has_time_filter", False):
            pattern = AntiPattern(
                name="unbounded_query",
                severity=Severity.HIGH,
                description=(
                    "Query without time filter: Full bucket scan without time bounds. "
                    "This can scan enormous amounts of data and cause performance issues."
                ),
                affected_table=normalized_plan.get("table_name"),
                affected_column=None,
                metadata={
                    "time_range": None,
                    "has_time_filter": False,
                },
            )
            anti_patterns.append(pattern)
            # Unbounded queries are CRITICAL in InfluxDB: deduct 30 points (not default 25)
            # Results in score <= 70 for unbounded queries
            self.scoring_engine.deduct("unbounded_query", Severity.HIGH, amount=30)

        # AP2: High-Cardinality Group-By
        group_by_columns = flux_metadata.get("group_by_columns", [])
        if len(group_by_columns) > 10:
            pattern = AntiPattern(
                name="high_cardinality_group_by",
                severity=Severity.MEDIUM,
                description=(
                    f"Group-by on {len(group_by_columns)} columns: "
                    "Risk of memory exhaustion and slow performance."
                ),
                affected_table=normalized_plan.get("table_name"),
                affected_column=None,
                metadata={
                    "column_count": len(group_by_columns),
                    "columns": group_by_columns,
                },
            )
            anti_patterns.append(pattern)
            self.scoring_engine.deduct("high_cardinality_group_by", Severity.MEDIUM)

        # AP3: Excessive Transformations
        transformation_count = flux_metadata.get("transformation_count", 0)
        if transformation_count > 5:
            pattern = AntiPattern(
                name="excessive_transformations",
                severity=Severity.MEDIUM,
                description=(
                    f"{transformation_count} transformations detected: "
                    "Consider simplifying pipeline by combining operations."
                ),
                affected_table=None,
                affected_column=None,
                metadata={
                    "transformation_count": transformation_count,
                },
            )
            anti_patterns.append(pattern)
            self.scoring_engine.deduct("excessive_transformations", Severity.MEDIUM)

        # AP4: Missing Field Filtering
        has_aggregation = flux_metadata.get("has_aggregation", False)
        operations = flux_metadata.get("operations", [])
        # Check if no explicit field selection before aggregation
        if not has_aggregation and not any("select" in op.lower() for op in operations):
            if transformation_count > 0:  # Only warn if there are transformations
                pattern = AntiPattern(
                    name="missing_field_filtering",
                    severity=Severity.LOW,
                    description=(
                        "No explicit field filtering detected: May return unnecessary fields. "
                        "Consider using select() to limit returned fields."
                    ),
                    affected_table=None,
                    affected_column=None,
                    metadata={},
                )
                anti_patterns.append(pattern)
                self.scoring_engine.deduct("missing_field_filtering", Severity.LOW)

        # Generate recommendations
        recommendations = self._generate_influxdb_recommendations(anti_patterns, flux_metadata)

        return DetectionResult(
            score=self.scoring_engine.get_score(),
            anti_patterns=anti_patterns,
            recommendations=recommendations,
        )

    def _generate_influxdb_recommendations(
        self, anti_patterns: list[AntiPattern], flux_metadata: dict[str, Any]
    ) -> list[str]:
        """Generate actionable recommendations for InfluxDB anti-patterns.

        Args:
            anti_patterns: List of detected anti-patterns
            flux_metadata: Flux-specific metadata from normalized plan

        Returns:
            List of specific recommendations
        """
        recommendations = []

        for ap in anti_patterns:
            if ap.name == "unbounded_query":
                rec = (
                    "Add time filter to query: "
                    "range(start: -24h, stop: now()) "
                    "to limit data scanned"
                )
                if rec not in recommendations:
                    recommendations.append(rec)

            elif ap.name == "high_cardinality_group_by":
                col_count = ap.metadata.get("column_count", 0)
                rec = (
                    f"Reduce group-by from {col_count} columns to < 10, "
                    "or add filters before grouping to reduce cardinality"
                )
                if rec not in recommendations:
                    recommendations.append(rec)

            elif ap.name == "excessive_transformations":
                transform_count = ap.metadata.get("transformation_count", 0)
                rec = (
                    f"Simplify pipeline: {transform_count} transformations detected. "
                    "Consider combining multiple map() operations into one."
                )
                if rec not in recommendations:
                    recommendations.append(rec)

            elif ap.name == "missing_field_filtering":
                rec = (
                    "Add field selection to limit returned fields: "
                    'use select(columns: ["field1", "field2"])'
                )
                if rec not in recommendations:
                    recommendations.append(rec)

        return recommendations

    def analyze_mongodb_patterns(
        self, normalized_plan: dict[str, Any], query: str = ""
    ) -> DetectionResult:
        """Analiza anti-patrones específicos de MongoDB.

        Args:
            normalized_plan: Plan normalizado de MongoExplainParser.parse()
            query: Query MongoDB original (para detecciones que lo requieren)

        Returns:
            DetectionResult con score, anti-patterns y recomendaciones
        """
        # Reset scoring para nuevo análisis
        self.scoring_engine = ScoringEngine()

        anti_patterns: list[AntiPattern] = []

        # Ejecuta todos los detectores MongoDB
        anti_patterns.extend(self._detect_mongodb_collection_scan(normalized_plan))
        anti_patterns.extend(self._detect_mongodb_high_doc_ratio(normalized_plan))
        anti_patterns.extend(self._detect_mongodb_sort_without_index(normalized_plan))
        anti_patterns.extend(self._detect_mongodb_regex_without_prefix(normalized_plan, query))

        # Genera recomendaciones específicas
        recommendations = self._generate_mongodb_recommendations(anti_patterns)

        return DetectionResult(
            score=self.scoring_engine.get_score(),
            anti_patterns=anti_patterns,
            recommendations=recommendations,
        )

    def _detect_mongodb_collection_scan(self, normalized_plan: dict[str, Any]) -> list[AntiPattern]:
        """Detecta COLLSCAN (collection scan completo).

        Severidad: ALTA (-25 puntos)
        """
        patterns: list[AntiPattern] = []

        if normalized_plan.get("has_collection_scan", False):
            docs_examined = normalized_plan.get("metrics", {}).get("documents_examined", 0)

            pattern = AntiPattern(
                name="collection_scan",
                severity=Severity.HIGH,
                description="Query realiza un collection scan completo (COLLSCAN)",
                affected_table=None,  # MongoDB no tiene tabla explícita
                affected_column=None,
                metadata={
                    "docs_examined": docs_examined,
                    "execution_time_ms": normalized_plan.get("metrics", {}).get(
                        "execution_time_ms", 0
                    ),
                },
            )
            patterns.append(pattern)
            self.scoring_engine.deduct("collection_scan", Severity.HIGH)

        return patterns

    def _detect_mongodb_high_doc_ratio(self, normalized_plan: dict[str, Any]) -> list[AntiPattern]:
        """Detecta alto ratio de documentos examinados vs retornados.

        Condición: docs_examined / docs_returned > 10
        Severidad: MEDIA (-15 puntos)
        """
        patterns: list[AntiPattern] = []

        metrics = normalized_plan.get("metrics", {})
        docs_returned = metrics.get("documents_returned", 0)
        docs_examined = metrics.get("documents_examined", 0)

        if docs_returned > 0 and docs_examined > 0:
            ratio = docs_examined / docs_returned

            if ratio > 10:
                pattern = AntiPattern(
                    name="high_doc_examination_ratio",
                    severity=Severity.MEDIUM,
                    description=(
                        f"Query examinó {docs_examined:,} documentos "
                        f"para retornar {docs_returned:,} ({ratio:.1f}x ratio)"
                    ),
                    affected_table=None,
                    affected_column=None,
                    metadata={
                        "ratio": ratio,
                        "docs_examined": docs_examined,
                        "docs_returned": docs_returned,
                    },
                )
                patterns.append(pattern)
                self.scoring_engine.deduct("high_doc_examination_ratio", Severity.MEDIUM)

        return patterns

    def _detect_mongodb_sort_without_index(
        self, normalized_plan: dict[str, Any]
    ) -> list[AntiPattern]:
        """Detecta sort en memoria (sin índice de soporte).

        Condición: has_sort=True AND has_index=False
        Severidad: MEDIA (-15 puntos)
        """
        patterns: list[AntiPattern] = []

        has_sort = normalized_plan.get("has_sort", False)
        has_index = normalized_plan.get("has_index", False)

        if has_sort and not has_index:
            pattern = AntiPattern(
                name="sort_without_index",
                severity=Severity.MEDIUM,
                description="Sort realizado en memoria (sin índice de soporte)",
                affected_table=None,
                affected_column=None,
                metadata={
                    "has_sort": True,
                    "has_index": False,
                },
            )
            patterns.append(pattern)
            self.scoring_engine.deduct("sort_without_index", Severity.MEDIUM)

        return patterns

    def _detect_mongodb_regex_without_prefix(
        self, normalized_plan: dict[str, Any], query: str = ""
    ) -> list[AntiPattern]:
        """Detecta regex sin anclaje de prefijo.

        Condición: query contiene operador $regex sin ^ al inicio
        Severidad: MEDIA (-15 puntos)
        """
        patterns: list[AntiPattern] = []

        if not query:
            return patterns

        # Búsqueda simple de $regex sin ancla
        import re

        regex_pattern = r"\$regex\s*:\s*['\"]([^'\"]+)['\"]"
        matches = re.findall(regex_pattern, query)

        for match in matches:
            # Si el regex no comienza con ^, es potencialmente problemático
            if not match.startswith("^"):
                pattern = AntiPattern(
                    name="regex_without_prefix",
                    severity=Severity.MEDIUM,
                    description=(
                        f"Regex sin anclaje de prefijo: '{match}' (requiere full collection scan)"
                    ),
                    affected_table=None,
                    affected_column=None,
                    metadata={
                        "regex_pattern": match,
                        "has_prefix_anchor": False,
                    },
                )
                patterns.append(pattern)
                self.scoring_engine.deduct("regex_without_prefix", Severity.MEDIUM)
                break  # Solo una advertencia por query

        return patterns

    def _generate_mongodb_recommendations(self, anti_patterns: list[AntiPattern]) -> list[str]:
        """Genera recomendaciones específicas para MongoDB.

        Args:
            anti_patterns: Lista de patrones detectados

        Returns:
            Lista de recomendaciones sin duplicados
        """
        recommendations: list[str] = []

        for ap in anti_patterns:
            if ap.name == "collection_scan":
                rec = RecommendationEngine.mongodb_collection_scan(
                    "collection",
                    ap.metadata.get("docs_examined", 0),
                )
                if rec not in recommendations:
                    recommendations.append(rec)

            elif ap.name == "high_doc_examination_ratio":
                rec = RecommendationEngine.mongodb_high_doc_ratio(
                    "collection",
                    ap.metadata.get("ratio", 1.0),
                    ap.metadata.get("docs_examined", 0),
                )
                if rec not in recommendations:
                    recommendations.append(rec)

            elif ap.name == "sort_without_index":
                rec = RecommendationEngine.mongodb_sort_without_index("collection", None)
                if rec not in recommendations:
                    recommendations.append(rec)

            elif ap.name == "regex_without_prefix":
                rec = RecommendationEngine.mongodb_regex_without_prefix(
                    "field", ap.metadata.get("regex_pattern")
                )
                if rec not in recommendations:
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
