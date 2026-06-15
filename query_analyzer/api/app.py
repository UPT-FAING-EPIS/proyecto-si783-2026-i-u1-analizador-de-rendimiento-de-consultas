"""FastAPI application for Query Analyzer."""

import os

import uvicorn
from fastapi import FastAPI

from query_analyzer import __version__
from query_analyzer.api.router import router

app = FastAPI(
    title="Query Analyzer API",
    description="API REST para obtener planes y métricas factuales de consultas.",
    version=__version__,
)
app.include_router(router, prefix="/api/v1")


def main() -> None:
    """Run the API server on the local development address."""
    host = os.environ.get("QA_API_HOST", "127.0.0.1")
    port = int(os.environ.get("QA_API_PORT", "8000"))
    uvicorn.run("query_analyzer.api.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
