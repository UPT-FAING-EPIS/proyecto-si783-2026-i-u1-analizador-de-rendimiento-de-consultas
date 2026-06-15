"""MCP server exposing Query Analyzer tools."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from query_analyzer.adapters import AdapterRegistry
from query_analyzer.config import ConfigManager

mcp = FastMCP("Query Analyzer", json_response=True)


def _resolve_connection_profile(profile: str | None) -> tuple[str, Any]:
    """Resolve the requested profile name and return its connection config."""
    config_manager = ConfigManager()
    app_config = config_manager.load_config()
    profile_name = profile or app_config.default_profile

    if not profile_name:
        raise ValueError(
            "No profile provided and no default profile configured. "
            "Create one with `qa profile add` or pass the profile argument."
        )

    return profile_name, config_manager.get_connection_config(profile_name)


def analyze_query_with_profile(query: str, profile: str | None = None) -> dict[str, Any]:
    """Analyze a query using a configured Query Analyzer profile."""
    if not query.strip():
        return {
            "success": False,
            "engine": "",
            "query": query,
            "error": "Query cannot be empty.",
        }

    try:
        profile_name, connection_config = _resolve_connection_profile(profile)
        adapter = AdapterRegistry.create(connection_config.engine, connection_config)

        with adapter:
            report = adapter.execute_explain(query)

        data = report.model_dump(mode="json")
        return {
            "success": True,
            "profile": profile_name,
            "engine": data["engine"],
            "query": data["query"],
            "execution_time_ms": data["execution_time_ms"],
            "plan_summary": data["plan_summary"],
            "metrics": data["metrics"],
            "raw_plan": data["raw_plan"],
            "analyzed_at": data["analyzed_at"],
            "error": None,
        }
    except Exception as error:
        return {
            "success": False,
            "engine": "",
            "query": query,
            "error": str(error),
        }


@mcp.tool()
def analyze_query(query: str, profile: str | None = None) -> dict[str, Any]:
    """Analyze database query performance using a Query Analyzer profile."""
    return analyze_query_with_profile(query=query, profile=profile)


def main() -> None:
    """Run the Query Analyzer MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
