"""Excepciones personalizadas para el módulo de configuración."""


class ConfigException(Exception):
    """Excepción base para errores de configuración."""

    pass


class ConfigNotFoundError(ConfigException):
    """El archivo de configuración no existe (y no se puede crear)."""

    pass


class ConfigValidationError(ConfigException):
    """El contenido del archivo de configuración es inválido."""

    pass


class EncryptionError(ConfigException):
    """Error durante el cifrado o descifrado de credenciales."""

    pass


class ProfileNotFoundError(ConfigException):
    """El perfil solicitado no existe."""

    pass


class EnvVarNotFoundError(ConfigException):
    """Una variable de entorno requerida no existe."""

    pass
