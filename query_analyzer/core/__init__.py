"""Core module - Motor de análisis de consultas."""

from query_analyzer.core.anti_pattern_detector import (
    AntiPattern,
    AntiPatternDetector,
    DetectionResult,
    DetectorConfig,
    RecommendationEngine,
    ScoringEngine,
    Severity,
)

__all__ = [
    "AntiPatternDetector",
    "AntiPattern",
    "DetectionResult",
    "DetectorConfig",
    "Severity",
    "ScoringEngine",
    "RecommendationEngine",
]
