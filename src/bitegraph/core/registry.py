"""Adapter registry and discovery."""

from typing import Any, Optional
from bitegraph.core.interfaces import Adapter


class AdapterRegistry:
    """
    Registry for managing and discovering adapters.

    Adapters are registered by source_id and can be looked up for compatibility.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        """
        Register an adapter by its source_id.

        Args:
            adapter: An object implementing the Adapter protocol

        Raises:
            ValueError: If an adapter with the same source_id is already registered
        """
        source_id = adapter.source_id()
        if source_id in self._adapters:
            raise ValueError(f"Adapter with source_id='{source_id}' is already registered")
        self._adapters[source_id] = adapter

    def get(self, source_id: str) -> Optional[Adapter]:
        """
        Retrieve an adapter by source_id.

        Args:
            source_id: The adapter's source_id

        Returns:
            The adapter, or None if not found
        """
        return self._adapters.get(source_id)

    def find_compatible(self, metadata: dict[str, Any]) -> Optional[Adapter]:
        """
        Find the first adapter that can parse data with the given metadata.

        Args:
            metadata: Context about the data (source, format, etc.)

        Returns:
            A compatible adapter, or None if no adapter matches
        """
        for adapter in self._adapters.values():
            if adapter.can_parse(metadata):
                return adapter
        return None

    def list_all(self) -> dict[str, Adapter]:
        """
        Return all registered adapters.

        Returns:
            Dictionary of source_id -> Adapter
        """
        return dict(self._adapters)
