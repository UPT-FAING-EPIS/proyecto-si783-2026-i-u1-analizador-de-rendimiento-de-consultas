"""Excepciones personalizadas para el módulo de configuración."""


class ConfigError(Exception):
    """Excepción base para errores de configuración."""

    pass


class ConfigNotFoundError(ConfigError):
    """El archivo de configuración no existe (y no se puede crear)."""

    pass


class ConfigValidationError(ConfigError):
    """El contenido del archivo de configuración es inválido."""

    pass


class EncryptionError(ConfigError):
    """Error durante el cifrado o descifrado de credenciales."""

    pass


class ProfileNotFoundError(ConfigError):
    """El perfil solicitado no existe."""

    pass


class EnvVarNotFoundError(ConfigError):
    """Una variable de entorno requerida no existe."""

    pass
