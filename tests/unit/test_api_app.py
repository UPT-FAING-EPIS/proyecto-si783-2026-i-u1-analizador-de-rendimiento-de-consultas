"""Tests for the FastAPI app entrypoint."""

import importlib
from unittest.mock import patch

api_app = importlib.import_module("query_analyzer.api.app")


def test_main_uses_default_api_host_and_port(monkeypatch) -> None:
    """API entrypoint defaults to the integrations port."""
    monkeypatch.delenv("QA_API_HOST", raising=False)
    monkeypatch.delenv("QA_API_PORT", raising=False)

    with patch("query_analyzer.api.app.uvicorn.run") as run:
        api_app.main()

    run.assert_called_once_with("query_analyzer.api.app:app", host="127.0.0.1", port=8000)


def test_main_uses_api_host_and_port_from_environment(monkeypatch) -> None:
    """API entrypoint allows local integration overrides."""
    monkeypatch.setenv("QA_API_HOST", "0.0.0.0")
    monkeypatch.setenv("QA_API_PORT", "8001")

    with patch("query_analyzer.api.app.uvicorn.run") as run:
        api_app.main()

    run.assert_called_once_with("query_analyzer.api.app:app", host="0.0.0.0", port=8001)
