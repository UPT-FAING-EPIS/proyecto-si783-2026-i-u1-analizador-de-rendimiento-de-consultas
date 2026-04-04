# Dockerfile para Query Analyzer
FROM python:3.14-slim

WORKDIR /app

# Instalar uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copiar proyecto
COPY . .

# Instalar dependencias
RUN uv sync --frozen

# Punto de entrada
ENTRYPOINT ["uv", "run", "query_analyzer"]
CMD ["--help"]
