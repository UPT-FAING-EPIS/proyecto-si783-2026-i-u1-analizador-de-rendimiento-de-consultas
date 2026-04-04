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


class UnsupportedEngineError(AdapterException):
    """Motor de base de datos no registrado o no soportado."""

    def __init__(self, engine_name: str, available_engines: list[str]) -> None:
        """
        Inicializa el error con nombre del motor y lista de disponibles.

        Args:
            engine_name: Nombre del motor solicitado
            available_engines: Lista de motores registrados
        """
        self.engine_name = engine_name
        self.available_engines = available_engines
        engines_list = ", ".join(available_engines) if available_engines else "ninguno"
        message = f"Motor '{engine_name}' no soportado. Disponibles: {engines_list}"
        super().__init__(message)
