"""Connection state manager for TUI.

Singleton that manages the active connection profile and adapter instance.
"""

from collections.abc import Iterable
from enum import Enum
from threading import Lock

from query_analyzer.adapters import AdapterRegistry, BaseAdapter
from query_analyzer.config import ConfigManager, ProfileConfig


class ConnectionStatus(Enum):
    """Estado actual de la conexión."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectionManager:
    """Gestor singleton del estado de conexión.

    Maneja:
    - Perfiles disponibles (carga desde ConfigManager)
    - Adapter activo e instancia de conexión
    - Estado de conexión (disconnected/connecting/connected/error)

    Uso:
        manager = ConnectionManager.get()
        profiles = manager.list_profiles()
        manager.connect("profile-name")
    """

    _instance: ConnectionManager | None = None
    _config_manager: ConfigManager | None = None
    _adapter: BaseAdapter | None = None
    _status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    _error_message: str | None = None
    _last_profile_name: str | None = None
    _last_attempted_profile_name: str | None = None
    _profile_statuses: dict[str, ConnectionStatus] = {}
    _profile_errors: dict[str, str | None] = {}
    _status_lock: Lock = Lock()

    @classmethod
    def get(cls) -> ConnectionManager:
        """Obtiene la instancia singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reinicia la instancia (para testing)."""
        cls._instance = None
        cls._config_manager = None
        cls._adapter = None
        cls._status = ConnectionStatus.DISCONNECTED
        cls._error_message = None
        cls._last_profile_name = None
        cls._last_attempted_profile_name = None
        cls._profile_statuses = {}
        cls._profile_errors = {}

    @property
    def config_manager(self) -> ConfigManager:
        """Obtiene ConfigManager lazy-loaded."""
        if self._config_manager is None:
            self._config_manager = ConfigManager()
        return self._config_manager

    def list_profiles(self) -> dict[str, ProfileConfig]:
        """Lista todos los perfiles disponibles.

        Returns:
            Diccionario nombre -> ProfileConfig
        """
        profiles = self.config_manager.list_profiles()
        self._ensure_profile_statuses(profiles.keys())
        return profiles

    def _ensure_profile_statuses(self, profile_names: Iterable[str]) -> None:
        names = list(profile_names)
        with self._status_lock:
            for name in names:
                if name not in self._profile_statuses:
                    self._profile_statuses[name] = ConnectionStatus.DISCONNECTED
                    self._profile_errors[name] = None

            for existing_name in list(self._profile_statuses):
                if existing_name not in names:
                    del self._profile_statuses[existing_name]
                    self._profile_errors.pop(existing_name, None)

    def get_profile(self, name: str) -> ProfileConfig:
        """Obtiene un perfil por nombre.

        Args:
            name: Nombre del perfil

        Returns:
            ProfileConfig

        Raises:
            ProfileNotFoundError: Si no existe
        """
        return self.config_manager.get_profile(name)

    @property
    def default_profile_name(self) -> str | None:
        """Nombre del perfil por defecto."""
        return self.config_manager.load_config().default_profile

    def set_default_profile(self, name: str) -> None:
        """Establece perfil por defecto."""
        self.config_manager.set_default_profile(name)
        self._last_profile_name = name

    @property
    def status(self) -> ConnectionStatus:
        """Estado actual de conexión."""
        return self._status

    @property
    def error_message(self) -> str | None:
        """Último mensaje de error."""
        return self._error_message

    @property
    def active_adapter(self) -> BaseAdapter | None:
        """Adapter activo."""
        return self._adapter

    @property
    def last_profile_name(self) -> str | None:
        """Último perfil usado."""
        return self._last_profile_name

    def mark_connecting(self, profile_name: str) -> None:
        """Marca un perfil en estado de conexión en curso."""
        self.set_profile_status(profile_name, ConnectionStatus.CONNECTING)

    def status_for_profile(self, profile_name: str) -> ConnectionStatus | None:
        """Retorna el estado de conexión para un perfil específico."""
        with self._status_lock:
            return self._profile_statuses.get(profile_name, ConnectionStatus.DISCONNECTED)

    def set_profile_status(
        self,
        profile_name: str,
        status: ConnectionStatus,
        error_message: str | None = None,
    ) -> None:
        """Actualiza el estado de conexión para un perfil."""
        with self._status_lock:
            self._profile_statuses[profile_name] = status
            self._profile_errors[profile_name] = error_message

        self._last_attempted_profile_name = profile_name
        self._status = status
        self._error_message = error_message

    def probe_profile(self, profile_name: str) -> ConnectionStatus:
        """Prueba conectividad de un perfil sin dejar una conexión abierta."""
        self.set_profile_status(profile_name, ConnectionStatus.CONNECTING)

        try:
            profile = self.get_profile(profile_name)
            connection_config = self.config_manager.get_connection_config(profile_name)

            if not AdapterRegistry.is_registered(profile.engine):
                from query_analyzer.adapters.exceptions import UnsupportedEngineError

                raise UnsupportedEngineError(profile.engine, AdapterRegistry.list_engines())

            adapter = AdapterRegistry.create(profile.engine, connection_config)
            try:
                adapter.connect()
                is_valid = adapter.test_connection()
            finally:
                try:
                    adapter.disconnect()
                except Exception:
                    pass

            if is_valid:
                self.set_profile_status(profile_name, ConnectionStatus.CONNECTED)
                return ConnectionStatus.CONNECTED

            self.set_profile_status(profile_name, ConnectionStatus.ERROR, "Connection test failed")
            return ConnectionStatus.ERROR
        except Exception as e:
            self.set_profile_status(profile_name, ConnectionStatus.ERROR, str(e))
            return ConnectionStatus.ERROR

    def add_profile(self, name: str, profile: ProfileConfig) -> None:
        """Agrega un nuevo perfil."""
        self.config_manager.add_profile(name, profile)
        self.set_profile_status(name, ConnectionStatus.DISCONNECTED)

    def delete_profile(self, name: str) -> None:
        """Elimina un perfil."""
        if self._last_profile_name == name:
            self.disconnect()
        self.config_manager.delete_profile(name)
        with self._status_lock:
            self._profile_statuses.pop(name, None)
            self._profile_errors.pop(name, None)

    def update_profile(self, name: str, profile: ProfileConfig) -> None:
        """Actualiza un perfil existente."""
        profiles = self.config_manager.list_profiles()
        if name not in profiles:
            from query_analyzer.config import ProfileNotFoundError

            raise ProfileNotFoundError(f"Perfil '{name}' no encontrado")
        self.config_manager.delete_profile(name)
        self.config_manager.add_profile(name, profile)
        self.set_profile_status(name, ConnectionStatus.DISCONNECTED)

    def connect(self, profile_name: str) -> bool:
        """Conecta al perfil especificado.

        Args:
            profile_name: Nombre del perfil

        Returns:
            True si la conexión fue exitosa

        Raises:
            ConnectionError: Si falla la conexión
        """
        profile = self.get_profile(profile_name)
        connection_config = self.config_manager.get_connection_config(profile_name)

        self.mark_connecting(profile_name)

        try:
            if not AdapterRegistry.is_registered(profile.engine):
                from query_analyzer.adapters.exceptions import UnsupportedEngineError

                raise UnsupportedEngineError(profile.engine, AdapterRegistry.list_engines())

            self._adapter = AdapterRegistry.create(profile.engine, connection_config)
            self._adapter.connect()

            if not self._adapter.test_connection():
                self.set_profile_status(
                    profile_name, ConnectionStatus.ERROR, "Connection test failed"
                )
                self._adapter = None
                return False

            self.set_profile_status(profile_name, ConnectionStatus.CONNECTED)
            self._last_profile_name = profile_name
            self.set_default_profile(profile_name)
            return True

        except Exception as e:
            self.set_profile_status(profile_name, ConnectionStatus.ERROR, str(e))
            if self._adapter:
                try:
                    self._adapter.disconnect()
                except Exception:
                    pass
            self._adapter = None
            raise

    def disconnect(self) -> None:
        """Desconecta y libera recursos."""
        if self._adapter:
            try:
                self._adapter.disconnect()
            except Exception:
                pass
            self._adapter = None
        if self._last_attempted_profile_name:
            self.set_profile_status(
                self._last_attempted_profile_name, ConnectionStatus.DISCONNECTED
            )
        else:
            self._status = ConnectionStatus.DISCONNECTED
            self._error_message = None
