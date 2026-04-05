"""Gestor central de configuración."""

import os
import re
from pathlib import Path
from typing import Any

import yaml

from query_analyzer.adapters import ConnectionConfig

from .crypto import CryptoManager
from .exceptions import (
    ConfigNotFoundError,
    ConfigValidationError,
    EnvVarNotFoundError,
    ProfileNotFoundError,
)
from .models import AppConfig, AppDefaults, ProfileConfig


class ConfigManager:
    """Gestor central de configuración de Query Analyzer.

    Responsabilidades:
    - Leer/escribir YAML
    - Interpolar variables de entorno
    - Cifrar/descifrar credenciales
    - Validar perfiles
    - Gestionar perfil default
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Inicializa el ConfigManager.

        Args:
            config_path: Ruta al config.yaml
                        Si None, usa ~/.query-analyzer/config.yaml
                        Puede ser sobrescrito por QA_CONFIG_PATH env var
        """
        # Permitir override con variable de entorno
        env_path = os.environ.get("QA_CONFIG_PATH")
        if env_path:
            self.config_path = Path(env_path)
        elif config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path.home() / ".query-analyzer" / "config.yaml"

        # Crear directorio si no existe
        self.config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        # Cargar configuración
        self._config = self._load_from_disk()

    def _load_from_disk(self) -> AppConfig:
        """Carga configuración desde disco.

        Si el archivo no existe, retorna una configuración vacía
        (el archivo se crea cuando se guarda).

        Returns:
            AppConfig cargada del disco
        """
        if not self.config_path.exists():
            return AppConfig()

        try:
            with open(self.config_path) as f:
                raw_data = yaml.safe_load(f)

            if raw_data is None:
                return AppConfig()

            # Interpolar variables de entorno ANTES de validar
            raw_data = self._interpolate_env_vars(raw_data)

            # Descifrar passwords
            raw_data = self._decrypt_passwords(raw_data)

            # Validar y convertir a AppConfig
            config = AppConfig(**raw_data)
            return config
        except (yaml.YAMLError, ValueError) as e:
            raise ConfigValidationError(f"Error al parsear {self.config_path}: {e}")

    def _interpolate_env_vars(self, data: Any) -> Any:
        """Interpola variables de entorno en forma ${VAR} o ${VAR:-default}.

        Args:
            data: Datos a interpolar (dict, list, str, etc)

        Returns:
            Datos con variables interpoladas

        Raises:
            EnvVarNotFoundError: Si una variable no existe y no tiene default
        """
        if isinstance(data, dict):
            return {k: self._interpolate_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._interpolate_env_vars(item) for item in data]
        elif isinstance(data, str):
            return self._interpolate_string(data)
        else:
            return data

    def _interpolate_string(self, value: str) -> str:
        """Interpola una cadena individual.

        Soporta:
        - ${VAR}: Variable obligatoria
        - ${VAR:-default}: Variable con valor default
        """
        # Patrón: ${VAR} o ${VAR:-default}
        pattern = r"\$\{([^}]+)\}"

        def replacer(match: Any) -> str:
            var_spec = match.group(1)

            # Verificar si hay valor default
            if ":-" in var_spec:
                var_name, default_value = var_spec.split(":-", 1)
            else:
                var_name = var_spec
                default_value = None

            # Obtener valor de env
            value = os.environ.get(var_name)
            if value is not None:
                return value
            elif default_value is not None:
                return default_value
            else:
                raise EnvVarNotFoundError(f"Variable de entorno no encontrada: {var_name}")

        return re.sub(pattern, replacer, value)

    def _decrypt_passwords(self, data: Any) -> Any:
        """Descifra passwords en datos cargados.

        Args:
            data: Datos del YAML

        Returns:
            Datos con passwords descifrados
        """
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if k == "profiles" and isinstance(v, dict):
                    # Descifrar passwords de perfiles
                    result[k] = {
                        profile_name: self._decrypt_profile(profile_data)
                        for profile_name, profile_data in v.items()
                    }
                else:
                    result[k] = self._decrypt_passwords(v)
            return result
        elif isinstance(data, list):
            return [self._decrypt_passwords(item) for item in data]
        else:
            return data

    def _decrypt_profile(self, profile_data: dict[str, Any]) -> dict[str, Any]:
        """Descifra el password de un perfil si está cifrado."""
        if "password" in profile_data and profile_data["password"]:
            password = profile_data["password"]
            if CryptoManager.is_encrypted(password):
                profile_data["password"] = CryptoManager.decrypt(password)
        return profile_data

    def _encrypt_passwords(self, data: Any) -> Any:
        """Cifra passwords antes de guardar.

        Args:
            data: Datos a guardar

        Returns:
            Datos con passwords cifrados
        """
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if k == "profiles" and isinstance(v, dict):
                    result[k] = {
                        profile_name: self._encrypt_profile(profile_data)
                        for profile_name, profile_data in v.items()
                    }
                else:
                    result[k] = self._encrypt_passwords(v)
            return result
        elif isinstance(data, list):
            return [self._encrypt_passwords(item) for item in data]
        else:
            return data

    def _encrypt_profile(self, profile_data: dict[str, Any]) -> dict[str, Any]:
        """Cifra el password de un perfil si no está vacío."""
        profile_data = profile_data.copy()
        if "password" in profile_data and profile_data["password"]:
            password = profile_data["password"]
            # Solo cifrar si no está ya cifrado
            if not CryptoManager.is_encrypted(password):
                profile_data["password"] = CryptoManager.encrypt(password)
        return profile_data

    def save_config(self) -> None:
        """Guarda la configuración actual a disco.

        Cifra passwords antes de guardar.
        """
        try:
            # Convertir a dict
            config_dict = self._config.model_dump()

            # Cifrar passwords
            config_dict = self._encrypt_passwords(config_dict)

            # Eliminar None values
            config_dict = {k: v for k, v in config_dict.items() if v is not None}

            # Crear directorio si no existe
            self.config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

            # Guardar a YAML
            with open(self.config_path, "w") as f:
                yaml.dump(
                    config_dict,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )

            # Permisos restrictivos
            self.config_path.chmod(0o600)
        except OSError as e:
            raise ConfigNotFoundError(f"Error al guardar configuración: {e}")

    def load_config(self) -> AppConfig:
        """Retorna la configuración actual cargada."""
        return self._config

    def add_profile(self, name: str, profile: ProfileConfig) -> None:
        """Agrega un nuevo perfil a la configuración.

        Args:
            name: Nombre del perfil
            profile: Configuración del perfil

        Raises:
            ConfigValidationError: Si el nombre ya existe
        """
        if name in self._config.profiles:
            raise ConfigValidationError(f"Perfil '{name}' ya existe")

        self._config.profiles[name] = profile
        self.save_config()

    def get_profile(self, name: str) -> ProfileConfig:
        """Obtiene un perfil por nombre.

        Args:
            name: Nombre del perfil

        Returns:
            ProfileConfig con el perfil

        Raises:
            ProfileNotFoundError: Si el perfil no existe
        """
        if name not in self._config.profiles:
            raise ProfileNotFoundError(f"Perfil '{name}' no encontrado")

        return self._config.profiles[name]

    def list_profiles(self) -> dict[str, ProfileConfig]:
        """Lista todos los perfiles.

        Returns:
            Diccionario de perfiles
        """
        return self._config.profiles.copy()

    def delete_profile(self, name: str) -> None:
        """Elimina un perfil.

        Args:
            name: Nombre del perfil

        Raises:
            ProfileNotFoundError: Si el perfil no existe
        """
        if name not in self._config.profiles:
            raise ProfileNotFoundError(f"Perfil '{name}' no encontrado")

        del self._config.profiles[name]

        # Si era el default, limpiar
        if self._config.default_profile == name:
            self._config.default_profile = None

        self.save_config()

    def set_default_profile(self, name: str) -> None:
        """Establece el perfil por defecto.

        Args:
            name: Nombre del perfil

        Raises:
            ProfileNotFoundError: Si el perfil no existe
        """
        if name not in self._config.profiles:
            raise ProfileNotFoundError(f"Perfil '{name}' no encontrado")

        self._config.default_profile = name
        self.save_config()

    def get_default_profile(self) -> ProfileConfig | None:
        """Obtiene el perfil por defecto actual.

        Returns:
            ProfileConfig del default o None si no hay
        """
        if self._config.default_profile is None:
            return None

        try:
            return self.get_profile(self._config.default_profile)
        except ProfileNotFoundError:
            # Profile fue eliminado, limpiar default
            self._config.default_profile = None
            self.save_config()
            return None

    def get_connection_config(self, profile_name: str) -> ConnectionConfig:
        """Convierte un ProfileConfig a ConnectionConfig.

        Args:
            profile_name: Nombre del perfil

        Returns:
            ConnectionConfig para usar con adapters

        Raises:
            ProfileNotFoundError: Si el perfil no existe
        """
        profile = self.get_profile(profile_name)

        return ConnectionConfig(
            engine=profile.engine,
            host=profile.host,
            port=profile.port,
            database=profile.database,
            username=profile.username,
            password=profile.password,
            extra=profile.extra,
        )

    def get_defaults(self) -> AppDefaults:
        """Obtiene la configuración de defaults."""
        return self._config.defaults
