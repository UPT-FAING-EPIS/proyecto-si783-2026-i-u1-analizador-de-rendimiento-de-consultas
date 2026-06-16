"""Tests for the API CLI command."""

from unittest.mock import patch

from typer.testing import CliRunner

from query_analyzer.cli.main import app

runner = CliRunner()


def test_api_command_passes_host_and_port_to_runner() -> None:
    """The bundled CLI can start the REST API with an explicit address."""
    with patch("query_analyzer.api.app.run_server") as run_server:
        result = runner.invoke(app, ["api", "--host", "127.0.0.1", "--port", "8765"])

    assert result.exit_code == 0
    run_server.assert_called_once_with(host="127.0.0.1", port=8765)
