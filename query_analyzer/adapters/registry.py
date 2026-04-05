"""Registro y factory para instanciar adapters por motor."""

from collections.abc import Callable

from .base import BaseAdapter
from .exceptions import UnsupportedEngineError
from .models import ConnectionConfig


class AdapterRegistry:
    """Registro centralizado de adapters con factory method.

    Permite registrar adapters con decorador y crearlos dinámicamente
    sin imports directos. Soporta lazy-loading de adapters.
    """

    _registry: dict[str, type[BaseAdapter]] = {}

    @classmethod
    def register(cls, engine_name: str) -> Callable[[type[BaseAdapter]], type[BaseAdapter]]:  # type: ignore[return]
        """Registra un adapter para un motor específico.

        Args:
            engine_name: Nombre del motor (ej: "postgresql", "mysql")

        Returns:
            Decorador que registra la clase adapter

        Raises:
            TypeError: Si la clase no hereda de BaseAdapter

        Example:
            @AdapterRegistry.register("postgresql")
            class PostgreSQLAdapter(BaseAdapter):
                pass
        """

        def decorator(adapter_class: type[BaseAdapter]) -> type[BaseAdapter]:
            if not issubclass(adapter_class, BaseAdapter):
                raise TypeError(f"Adapter '{adapter_class.__name__}' debe heredar de BaseAdapter")
            cls._registry[engine_name.lower()] = adapter_class
            return adapter_class

        return decorator

    @classmethod
    def create(cls, engine_name: str, config: ConnectionConfig) -> BaseAdapter:
        """Crea instancia de adapter para el motor especificado.

        Args:
            engine_name: Nombre del motor (ej: "postgresql")
            config: Configuración de conexión

        Returns:
            Instancia de adapter

        Raises:
            UnsupportedEngineError: Si motor no está registrado
        """
        engine_key = engine_name.lower()
        if engine_key not in cls._registry:
            raise UnsupportedEngineError(engine_name, cls.list_engines())

        adapter_class = cls._registry[engine_key]
        return adapter_class(config)

    @classmethod
    def list_engines(cls) -> list[str]:
        """Retorna lista ordenada de motores disponibles.

        Returns:
            Lista de nombres de motores registrados
        """
        return sorted(cls._registry.keys())

    @classmethod
    def is_registered(cls, engine_name: str) -> bool:
        """Verifica si un motor está registrado.

        Args:
            engine_name: Nombre del motor

        Returns:
            True si está registrado, False en otro caso
        """
        return engine_name.lower() in cls._registry
