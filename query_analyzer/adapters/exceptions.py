"""Excepciones personalizadas para el módulo de adapters."""


class AdapterException(Exception):
    """Excepción base para todos los errores de adapters."""

    pass


class ConnectionError(AdapterException):
    """Error al conectar a la base de datos."""

    pass


class ConnectionConfigError(AdapterException):
    """Error en la configuración de conexión (validación Pydantic)."""

    pass


class QueryAnalysisError(AdapterException):
    """Error durante el análisis de la query."""

    pass


class DisconnectionError(AdapterException):
    """Error al desconectar de la base de datos."""

    pass
