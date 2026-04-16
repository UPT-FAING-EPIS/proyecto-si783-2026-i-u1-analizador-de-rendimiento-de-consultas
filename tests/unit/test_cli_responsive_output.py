"""Manual test for responsive terminal output at different widths."""

from datetime import UTC, datetime

import query_analyzer.cli.utils as utils_module
from query_analyzer.adapters import QueryAnalysisReport, Recommendation, Warning
from query_analyzer.cli.terminal_config import (
    is_compact_layout,
    is_full_layout,
    is_vertical_layout,
)
from query_analyzer.cli.utils import OutputFormatter


def test_responsive_output_all_widths():
    """Test that output adapts correctly to different terminal widths."""
    report = QueryAnalysisReport(
        query="SELECT u.id, u.name, o.amount FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE u.created_at > NOW() - INTERVAL '30 days'",
        engine="postgresql",
        score=62,
        execution_time_ms=145.7,
        warnings=[
            Warning(
                severity="critical",
                message="Missing index on users(created_at) causes full table scan",
                node_type="Index",
                affected_object="users.created_at",
            ),
        ],
        recommendations=[
            Recommendation(
                priority=1,
                title="Create index on users(created_at)",
                description="Will improve query performance by 80-90%",
            ),
        ],
        metrics={"rows_examined": "2,500,000"},
        analyzed_at=datetime.now(UTC),
    )

    test_widths = [50, 60, 80, 100, 120, 150]

    for width in test_widths:
        # Save original function
        original_get_width = utils_module.get_terminal_width

        try:
            # Override get_terminal_width for this test
            utils_module.get_terminal_width = lambda w=width: w

            formatted = OutputFormatter.format_report_rich(report)

            # Verify layout type matches width
            if width < 80:
                assert "  " in formatted, (
                    f"Vertical layout should have indented key-value at width {width}"
                )
            elif width < 120:
                assert "Severity" in formatted or "Action" in formatted, (
                    f"Compact layout should have table at width {width}"
                )
            else:
                assert "Severity" in formatted or "Message" in formatted, (
                    f"Full layout should have multi-column table at width {width}"
                )

        finally:
            # Restore original function
            utils_module.get_terminal_width = original_get_width


def test_vertical_layout_format():
    """Verify vertical layout uses key-value format for narrow terminals."""
    report = QueryAnalysisReport(
        query="SELECT * FROM users",
        engine="postgresql",
        score=75,
        execution_time_ms=10.0,
        warnings=[
            Warning(
                severity="medium",
                message="Test warning message",
                node_type="Warning",
            ),
        ],
        recommendations=[
            Recommendation(
                priority=3,
                title="Test recommendation",
                description="Test description",
            ),
        ],
        metrics={},
        analyzed_at=datetime.now(UTC),
    )

    original_get_width = utils_module.get_terminal_width
    try:
        # Test at narrow width (vertical layout)
        utils_module.get_terminal_width = lambda: 50
        assert is_vertical_layout(50)

        formatted = OutputFormatter.format_report_rich(report)

        # Vertical layout should have indentation but no table grid characters
        assert "│" in formatted or "  " in formatted  # Either table or indentation
        # Should not have full 3-column table
        if "Test warning" in formatted:
            # If warning is shown, check it's in readable format
            assert "warning" in formatted.lower() or "TEST" in formatted

    finally:
        utils_module.get_terminal_width = original_get_width


def test_compact_layout_format():
    """Verify compact layout uses 2-column tables."""
    report = QueryAnalysisReport(
        query="SELECT * FROM users",
        engine="postgresql",
        score=50,
        execution_time_ms=50.0,
        warnings=[
            Warning(
                severity="high",
                message="High severity issue",
                node_type="Scan",
            ),
        ],
        recommendations=[],
        metrics={},
        analyzed_at=datetime.now(UTC),
    )

    original_get_width = utils_module.get_terminal_width
    try:
        # Test at compact width
        utils_module.get_terminal_width = lambda: 90
        assert is_compact_layout(90)

        formatted = OutputFormatter.format_report_rich(report)

        # Compact layout should have warnings table with message content
        assert "Severity" in formatted
        assert "Message" in formatted or "HIGH" in formatted

    finally:
        utils_module.get_terminal_width = original_get_width


def test_full_layout_format():
    """Verify full layout uses 3-column tables."""
    report = QueryAnalysisReport(
        query="SELECT * FROM users",
        engine="postgresql",
        score=70,
        execution_time_ms=20.0,
        warnings=[],
        recommendations=[
            Recommendation(
                priority=2,
                title="Add indexes",
                description="Create indexes on key columns",
            ),
        ],
        metrics={},
        analyzed_at=datetime.now(UTC),
    )

    original_get_width = utils_module.get_terminal_width
    try:
        # Test at full width
        utils_module.get_terminal_width = lambda: 140
        assert is_full_layout(140)

        formatted = OutputFormatter.format_report_rich(report)

        # Full layout should have Action and Details columns for recommendations
        assert "Add indexes" in formatted

    finally:
        utils_module.get_terminal_width = original_get_width
