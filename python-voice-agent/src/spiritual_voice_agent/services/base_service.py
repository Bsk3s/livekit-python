from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseService(ABC):
    """Base class for all services in the system."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate the service configuration."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if the service is properly initialized."""
        pass

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Get the name of the service."""
        pass
