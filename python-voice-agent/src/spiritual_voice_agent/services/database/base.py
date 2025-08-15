"""
Database Adapter Base Classes

Provides the abstract interface for database operations with support
for both SQLite and PostgreSQL backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    type: str  # 'sqlite' or 'postgresql'
    url: Optional[str] = None  # Full connection URL
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    pool_size: int = 10
    max_overflow: int = 20
    sqlite_path: str = "logs/cost_analytics.db"
    
    def get_connection_string(self) -> str:
        """Get database connection string"""
        if self.url:
            return self.url
        elif self.type == 'postgresql':
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.type == 'sqlite':
            return f"sqlite:///{self.sqlite_path}"
        else:
            raise ValueError(f"Unsupported database type: {self.type}")


class DatabaseAdapter(ABC):
    """
    Abstract database adapter interface
    
    Provides consistent interface for database operations regardless of backend.
    Enables zero-impact migration from SQLite to PostgreSQL.
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database connection and schema"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connections"""
        pass
    
    @abstractmethod
    async def create_tables(self) -> None:
        """Create database tables and indexes"""
        pass
    
    @abstractmethod
    async def insert_cost_event(self, event_data: Dict[str, Any]) -> int:
        """Insert a cost event and return the ID"""
        pass
    
    @abstractmethod
    async def update_cost_calculation(self, event_id: int, costs: Dict[str, Any]) -> None:
        """Update cost calculations for an event"""
        pass
    
    @abstractmethod
    async def get_session_costs(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all cost events for a session"""
        pass
    
    @abstractmethod
    async def get_user_costs(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get cost events for a user within specified days"""
        pass
    
    @abstractmethod
    async def get_cost_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get cost summary for dashboard"""
        pass
    
    @abstractmethod
    async def get_user_cost_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get cost summary for specific user"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if database is healthy and responsive"""
        pass
    
    @property
    def is_initialized(self) -> bool:
        """Check if adapter is initialized"""
        return self._initialized
    
    async def __aenter__(self):
        """Async context manager entry"""
        if not self._initialized:
            await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


class DatabaseError(Exception):
    """Base exception for database operations"""
    pass


class ConnectionError(DatabaseError):
    """Database connection error"""
    pass


class QueryError(DatabaseError):
    """Database query error"""
    pass


class MigrationError(DatabaseError):
    """Database migration error"""
    pass