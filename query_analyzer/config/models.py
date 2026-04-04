"""Modelos de configuración para perfiles y valores por defecto."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileConfig(BaseModel):  # type: ignore[misc]
    """
    Configuración de un perfil de conexión.

    Attributes:
        engine: Motor de base de datos (postgresql, mysql)
        host: Dirección del servidor
        port: Puerto de conexión
        database: Nombre de la base de datos
        username: Usuario para autenticación
        password: Contraseña (será cifrada en disco)
        extra: Parámetros adicionales específicos del motor
    """

    engine: str
    host: str
    port: int
    database: str
    username: str
    password: str
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("engine")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_engine(cls, v: str) -> str:
        """Valida que el engine sea soportado."""
        valid_engines = {"postgresql", "mysql"}
        engine_lower = v.lower()
        if engine_lower not in valid_engines:
            raise ValueError(
                f"Engine no soportado: {v}. Válidos: {', '.join(valid_engines)}"
            )
        return engine_lower

    @field_validator("port")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Valida que el puerto esté en rango válido."""
        if not (1 <= v <= 65535):
            raise ValueError(f"Puerto debe estar entre 1 y 65535, recibido: {v}")
        return v


class AppDefaults(BaseModel):  # type: ignore[misc]
    """
    Configuraciones por defecto de la aplicación.

    Attributes:
        slow_query_threshold_ms: Umbral para considerar query lenta
        explain_format: Formato del plan de ejecución (json, text)
        output_format: Formato de salida (rich, plain, json)
    """

    slow_query_threshold_ms: int = 1000
    explain_format: str = "json"
    output_format: str = "rich"

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("slow_query_threshold_ms")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_threshold(cls, v: int) -> int:
        """Valida que el threshold sea positivo."""
        if v < 0:
            raise ValueError(f"Threshold debe ser >= 0, recibido: {v}")
        return v

    @field_validator("explain_format")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_explain_format(cls, v: str) -> str:
        """Valida formato de explicación."""
        valid = {"json", "text"}
        if v.lower() not in valid:
            raise ValueError(f"Format debe ser: {', '.join(valid)}")
        return v.lower()

    @field_validator("output_format")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Valida formato de salida."""
        valid = {"rich", "plain", "json"}
        if v.lower() not in valid:
            raise ValueError(f"Format debe ser: {', '.join(valid)}")
        return v.lower()


class AppConfig(BaseModel):  # type: ignore[misc]
    """
    Configuración completa de la aplicación.

    Attributes:
        profiles: Diccionario de perfiles de conexión
        defaults: Configuraciones por defecto
        default_profile: Nombre del perfil activo actual
    """

    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    defaults: AppDefaults = Field(default_factory=AppDefaults)
    default_profile: Optional[str] = None

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("default_profile")  # type: ignore[untyped-decorator]
    @classmethod
    def validate_default_profile(cls, v: Optional[str], info: Any) -> Optional[str]:
        """Valida que el default_profile exista si se especifica."""
        if v is None:
            return v
        # En validación, no tenemos acceso a profiles aún
        # Se valida en ConfigManager
        return v
