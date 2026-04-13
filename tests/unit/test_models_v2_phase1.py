"""Unit tests para FASE 1: Models, Serializer, Renderer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from query_analyzer.adapters.models import (
    PlanNode,
    QueryAnalysisReport,
    Recommendation,
    Warning,
)
from query_analyzer.adapters.serializer import ReportSerializer
from query_analyzer.tui.report_renderer import ReportRenderer

# ========== FIXTURES ==========


@pytest.fixture
def sample_plan_node() -> PlanNode:
    """Crea un PlanNode sample con estructura jerárquica."""
    return PlanNode(
        node_type="Seq Scan",
        cost=1000.0,
        estimated_rows=50000,
        actual_rows=50000,
        actual_time_ms=145.23,
        children=[
            PlanNode(
                node_type="Filter",
                cost=100.0,
                estimated_rows=5000,
                actual_rows=4500,
                actual_time_ms=50.0,
                properties={"filter_condition": "age > 30"},
            )
        ],
        properties={"table_name": "users", "index_used": False},
    )


@pytest.fixture
def sample_warning() -> Warning:
    """Crea un Warning sample."""
    return Warning(
        severity="critical",
        message="Full table scan on users (50000 rows)",
        node_type="Seq Scan",
        affected_object="users",
        metadata={"rows": 50000, "threshold": 10000},
    )


@pytest.fixture
def sample_recommendation() -> Recommendation:
    """Crea un Recommendation sample."""
    return Recommendation(
        priority=1,
        title="Add index on users(age)",
        description="Creating an index on the age column will improve query performance for age-based filters.",
        code_snippet="CREATE INDEX idx_users_age ON users(age);",
        affected_object="users",
        metadata={"type": "index", "columns": ["age"]},
    )


@pytest.fixture
def sample_report(
    sample_plan_node: PlanNode,
    sample_warning: Warning,
    sample_recommendation: Recommendation,
) -> QueryAnalysisReport:
    """Crea un QueryAnalysisReport v2 sample."""
    return QueryAnalysisReport(
        engine="postgresql",
        query="SELECT * FROM users WHERE age > 30",
        score=75,
        execution_time_ms=145.23,
        warnings=[sample_warning],
        recommendations=[sample_recommendation],
        plan_tree=sample_plan_node,
        analyzed_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
        raw_plan={"Plan": {"Node Type": "Seq Scan"}},
        metrics={"node_count": 2, "buffers_hit": 1200},
    )


# ========== TESTS: MODELS ==========


class TestPlanNode:
    """Tests para PlanNode dataclass."""

    def test_plan_node_creation(self, sample_plan_node: PlanNode) -> None:
        """Verifica que PlanNode se crea correctamente."""
        assert sample_plan_node.node_type == "Seq Scan"
        assert sample_plan_node.cost == 1000.0
        assert sample_plan_node.actual_rows == 50000
        assert len(sample_plan_node.children) == 1

    def test_plan_node_recursive_structure(self, sample_plan_node: PlanNode) -> None:
        """Verifica que la estructura recursiva funciona."""
        child = sample_plan_node.children[0]
        assert child.node_type == "Filter"
        assert child.properties["filter_condition"] == "age > 30"

    def test_plan_node_properties_dict(self, sample_plan_node: PlanNode) -> None:
        """Verifica que properties preserva datos motor-específicos."""
        assert sample_plan_node.properties["table_name"] == "users"
        assert sample_plan_node.properties["index_used"] is False

    def test_plan_node_empty_node_type_fails(self) -> None:
        """Verifica que node_type no puede estar vacío."""
        with pytest.raises(ValueError, match="node_type no puede estar vacío"):
            PlanNode(node_type="")

    def test_plan_node_optional_fields(self) -> None:
        """Verifica que los campos opcionales se manejan correctamente."""
        node = PlanNode(node_type="Unknown")
        assert node.cost is None
        assert node.estimated_rows is None
        assert node.children == []


class TestWarning:
    """Tests para Warning dataclass."""

    def test_warning_creation(self, sample_warning: Warning) -> None:
        """Verifica que Warning se crea correctamente."""
        assert sample_warning.severity == "critical"
        assert sample_warning.message == "Full table scan on users (50000 rows)"
        assert sample_warning.affected_object == "users"

    def test_warning_severity_values(self) -> None:
        """Verifica que severity solo acepta valores válidos."""
        for severity in ["critical", "high", "medium", "low"]:
            warning = Warning(severity=severity, message="Test")
            assert warning.severity == severity

    def test_warning_invalid_severity_fails(self) -> None:
        """Verifica que severidad inválida falla."""
        with pytest.raises(ValueError):
            Warning(severity="invalid", message="Test")

    def test_warning_metadata(self, sample_warning: Warning) -> None:
        """Verifica que metadata preserva información adicional."""
        assert sample_warning.metadata["rows"] == 50000
        assert sample_warning.metadata["threshold"] == 10000

    def test_warning_empty_message_fails(self) -> None:
        """Verifica que message no puede estar vacío."""
        with pytest.raises(ValueError, match="message no puede estar vacío"):
            Warning(severity="high", message="")


class TestRecommendation:
    """Tests para Recommendation dataclass."""

    def test_recommendation_creation(self, sample_recommendation: Recommendation) -> None:
        """Verifica que Recommendation se crea correctamente."""
        assert sample_recommendation.priority == 1
        assert sample_recommendation.title == "Add index on users(age)"
        assert sample_recommendation.code_snippet is not None

    def test_recommendation_priority_range(self) -> None:
        """Verifica que priority está entre 1-10."""
        for priority in [1, 5, 10]:
            rec = Recommendation(priority=priority, title="Test", description="Test")
            assert rec.priority == priority

    def test_recommendation_invalid_priority_fails(self) -> None:
        """Verifica que priority fuera de rango falla."""
        with pytest.raises(ValueError, match="priority debe estar entre 1 y 10"):
            Recommendation(priority=11, title="Test", description="Test")

    def test_recommendation_empty_title_fails(self) -> None:
        """Verifica que title no puede estar vacío."""
        with pytest.raises(ValueError, match="title no puede estar vacío"):
            Recommendation(priority=1, title="", description="Test")

    def test_recommendation_code_snippet_optional(self) -> None:
        """Verifica que code_snippet es opcional."""
        rec = Recommendation(priority=5, title="Test", description="Test")
        assert rec.code_snippet is None


class TestQueryAnalysisReport:
    """Tests para QueryAnalysisReport dataclass."""

    def test_report_creation(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que QueryAnalysisReport v2 se crea correctamente."""
        assert sample_report.engine == "postgresql"
        assert sample_report.score == 75
        assert len(sample_report.warnings) == 1
        assert len(sample_report.recommendations) == 1
        assert sample_report.plan_tree is not None

    def test_report_score_range(self) -> None:
        """Verifica que score está entre 0-100."""
        for score in [0, 50, 100]:
            report = QueryAnalysisReport(
                engine="postgresql",
                query="SELECT 1",
                score=score,
                execution_time_ms=10.0,
            )
            assert report.score == score

    def test_report_invalid_score_fails(self) -> None:
        """Verifica que score fuera de rango falla."""
        with pytest.raises(ValueError):
            QueryAnalysisReport(
                engine="postgresql",
                query="SELECT 1",
                score=101,
                execution_time_ms=10.0,
            )

    def test_report_analyzed_at_utc(self) -> None:
        """Verifica que analyzed_at siempre es UTC."""
        report = QueryAnalysisReport(
            engine="postgresql",
            query="SELECT 1",
            score=50,
            execution_time_ms=10.0,
        )
        assert report.analyzed_at.tzinfo == UTC

    def test_report_backward_compatibility(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que raw_plan y metrics se preservan."""
        assert sample_report.raw_plan is not None
        assert sample_report.metrics["node_count"] == 2


# ========== TESTS: SERIALIZER ==========


class TestReportSerializerJSON:
    """Tests para JSON serialization del ReportSerializer."""

    def test_to_json_valid(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que to_json genera JSON válido."""
        json_str = ReportSerializer.to_json(sample_report)
        assert isinstance(json_str, str)
        assert "postgresql" in json_str
        assert sample_report.query in json_str

    def test_from_json_valid(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que from_json reconstruye el reporte."""
        json_str = ReportSerializer.to_json(sample_report)
        report2 = ReportSerializer.from_json(json_str)

        assert report2.engine == sample_report.engine
        assert report2.score == sample_report.score
        assert len(report2.warnings) == len(sample_report.warnings)
        assert len(report2.recommendations) == len(sample_report.recommendations)

    def test_json_roundtrip(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que JSON roundtrip preserva datos."""
        json_str = ReportSerializer.to_json(sample_report)
        report2 = ReportSerializer.from_json(json_str)
        json_str2 = ReportSerializer.to_json(report2)

        # Los JSONs deben ser idénticos (sin diferencias de orden)
        report3 = ReportSerializer.from_json(json_str2)
        assert report3.score == sample_report.score

    def test_json_preserves_timezone(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que analyzed_at preserva UTC en roundtrip."""
        json_str = ReportSerializer.to_json(sample_report)
        report2 = ReportSerializer.from_json(json_str)

        assert report2.analyzed_at.tzinfo == UTC
        assert report2.analyzed_at == sample_report.analyzed_at

    def test_json_with_plan_tree(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que plan_tree se serializa correctamente."""
        json_str = ReportSerializer.to_json(sample_report)
        report2 = ReportSerializer.from_json(json_str)

        assert report2.plan_tree is not None
        assert report2.plan_tree.node_type == "Seq Scan"
        assert len(report2.plan_tree.children) == 1

    def test_from_json_invalid_fails(self) -> None:
        """Verifica que JSON inválido falla."""
        with pytest.raises(ValueError, match="Error deserializando JSON"):
            ReportSerializer.from_json("not valid json")


class TestReportSerializerMarkdown:
    """Tests para Markdown export del ReportSerializer."""

    def test_to_markdown_valid(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que to_markdown genera Markdown válido."""
        md = ReportSerializer.to_markdown(sample_report)
        assert isinstance(md, str)
        assert "# Query Analysis Report" in md
        assert "## Query" in md
        assert "SELECT * FROM users WHERE age > 30" in md

    def test_to_markdown_includes_warnings(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que Markdown incluye sección Warnings."""
        md = ReportSerializer.to_markdown(sample_report)
        assert "## Warnings" in md
        assert "Full table scan on users" in md

    def test_to_markdown_includes_recommendations(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que Markdown incluye sección Recommendations."""
        md = ReportSerializer.to_markdown(sample_report)
        assert "## Recommendations" in md
        assert "Add index on users(age)" in md
        assert "CREATE INDEX" in md

    def test_to_markdown_includes_plan(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que Markdown incluye sección Execution Plan."""
        md = ReportSerializer.to_markdown(sample_report)
        assert "## Execution Plan" in md
        assert "Seq Scan" in md

    def test_to_markdown_summary_table(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que Markdown incluye tabla de resumen."""
        md = ReportSerializer.to_markdown(sample_report)
        assert "| **Engine** | POSTGRESQL |" in md
        assert "| **Score** | 75/100 |" in md
        assert "| **Execution Time** |" in md

    def test_to_markdown_isoformat_analyzed_at(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que analyzed_at está en ISO format."""
        md = ReportSerializer.to_markdown(sample_report)
        assert "2024-01-15T10:30:00" in md


class TestReportSerializerFile:
    """Tests para file export del ReportSerializer."""

    def test_export_json_file(self, sample_report: QueryAnalysisReport, tmp_path) -> None:
        """Verifica que export_file crea archivo JSON válido."""
        filepath = tmp_path / "report.json"
        ReportSerializer.export_file(sample_report, str(filepath), format="json")

        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        report2 = ReportSerializer.from_json(content)
        assert report2.score == sample_report.score

    def test_export_markdown_file(self, sample_report: QueryAnalysisReport, tmp_path) -> None:
        """Verifica que export_file crea archivo Markdown válido."""
        filepath = tmp_path / "report.md"
        ReportSerializer.export_file(sample_report, str(filepath), format="md")

        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "# Query Analysis Report" in content
        assert "POSTGRESQL" in content

    def test_export_creates_directories(self, sample_report: QueryAnalysisReport, tmp_path) -> None:
        """Verifica que export_file crea directorios necesarios."""
        filepath = tmp_path / "subdir" / "deep" / "report.json"
        ReportSerializer.export_file(sample_report, str(filepath), format="json")

        assert filepath.exists()
        assert filepath.parent.exists()

    def test_export_invalid_format_fails(
        self, sample_report: QueryAnalysisReport, tmp_path
    ) -> None:
        """Verifica que formato inválido falla."""
        filepath = tmp_path / "report.txt"
        with pytest.raises(ValueError, match="Format debe ser"):
            ReportSerializer.export_file(sample_report, str(filepath), format="txt")


# ========== TESTS: RENDERER ==========


class TestReportRenderer:
    """Tests para ReportRenderer TUI."""

    def test_render_summary_returns_panel(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que render_summary retorna un Panel."""
        panel = ReportRenderer.render_summary(sample_report)
        from rich.panel import Panel

        assert isinstance(panel, Panel)

    def test_render_warnings_returns_table(self, sample_warning: Warning) -> None:
        """Verifica que render_warnings retorna una Table."""
        table = ReportRenderer.render_warnings([sample_warning])
        assert table is not None

    def test_render_warnings_empty_list(self) -> None:
        """Verifica que warnings vacío retorna tabla vacía."""
        table = ReportRenderer.render_warnings([])
        assert table is not None

    def test_render_recommendations_returns_group(
        self, sample_recommendation: Recommendation
    ) -> None:
        """Verifica que render_recommendations retorna un Group."""
        group = ReportRenderer.render_recommendations([sample_recommendation])
        assert group is not None

    def test_render_plan_tree_returns_tree(self, sample_plan_node: PlanNode) -> None:
        """Verifica que render_plan_tree retorna un Tree."""
        tree = ReportRenderer.render_plan_tree(sample_plan_node)
        assert tree is not None

    def test_render_plan_tree_none(self) -> None:
        """Verifica que plan_tree None se maneja correctamente."""
        tree = ReportRenderer.render_plan_tree(None)
        assert tree is not None

    def test_render_full_report_returns_group(self, sample_report: QueryAnalysisReport) -> None:
        """Verifica que render_full_report retorna un Group."""
        group = ReportRenderer.render_full_report(sample_report)
        assert group is not None

    def test_detect_code_language_sql(self) -> None:
        """Verifica que detecta SQL correctamente."""
        assert ReportRenderer._detect_code_language("SELECT * FROM users") == "sql"
        assert ReportRenderer._detect_code_language("CREATE INDEX idx ON tbl") == "sql"

    def test_detect_code_language_flux(self) -> None:
        """Verifica que detecta Flux correctamente."""
        assert ReportRenderer._detect_code_language("data |> range(start: -24h)") == "flux"

    def test_detect_code_language_cypher(self) -> None:
        """Verifica que detecta Cypher correctamente."""
        assert ReportRenderer._detect_code_language("MATCH (n:User) RETURN n") == "cypher"

    def test_get_score_color(self) -> None:
        """Verifica que score coloring funciona correctamente."""
        assert ReportRenderer._get_score_color(95) == "bright_green"
        assert ReportRenderer._get_score_color(75) == "green"
        assert ReportRenderer._get_score_color(55) == "yellow"
        assert ReportRenderer._get_score_color(35) == "orange1"
        assert ReportRenderer._get_score_color(15) == "red"
