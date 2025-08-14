"""
Database Factory

Creates database adapters based on configuration with automatic fallback
and connection validation for seamless development to production migration.
"""

import logging
from typing import Optional

from .base import DatabaseAdapter, DatabaseConfig, ConnectionError
from .sqlite_adapter import SQLiteAdapter
from .postgresql_adapter import PostgreSQLAdapter

logger = logging.getLogger(__name__)

# Global database adapter instance
_database_adapter: Optional[DatabaseAdapter] = None


def create_database_adapter(config: DatabaseConfig) -> DatabaseAdapter:
    """
    Create database adapter based on configuration
    
    Args:
        config: Database configuration
        
    Returns:
        DatabaseAdapter: Configured database adapter
        
    Raises:
        ValueError: If database type is unsupported
        ConnectionError: If database connection fails
    """
    if config.type == 'sqlite':
        logger.info("🗄️ Creating SQLite database adapter")
        return SQLiteAdapter(config)
    elif config.type == 'postgresql':
        logger.info("🐘 Creating PostgreSQL database adapter")
        return PostgreSQLAdapter(config)
    else:
        raise ValueError(f"Unsupported database type: {config.type}")


async def get_database_adapter(config: Optional[DatabaseConfig] = None) -> DatabaseAdapter:
    """
    Get global database adapter instance with lazy initialization
    
    Args:
        config: Optional database configuration (for initialization)
        
    Returns:
        DatabaseAdapter: Global database adapter instance
        
    Raises:
        RuntimeError: If adapter not initialized and no config provided
    """
    global _database_adapter
    
    if _database_adapter is None:
        if config is None:
            raise RuntimeError("Database adapter not initialized and no config provided")
        
        _database_adapter = create_database_adapter(config)
        await _database_adapter.initialize()
    
    return _database_adapter


async def close_database_adapter():
    """Close global database adapter"""
    global _database_adapter
    
    if _database_adapter:
        await _database_adapter.close()
        _database_adapter = None


def reset_database_adapter():
    """Reset global database adapter (for testing)"""
    global _database_adapter
    _database_adapter = None


class DatabaseManager:
    """
    Database manager with automatic failover and health monitoring
    
    Provides high-level database operations with automatic SQLite fallback
    if PostgreSQL is unavailable, ensuring zero-downtime deployment.
    """
    
    def __init__(self, primary_config: DatabaseConfig, fallback_config: Optional[DatabaseConfig] = None):
        self.primary_config = primary_config
        self.fallback_config = fallback_config
        self.adapter: Optional[DatabaseAdapter] = None
        self.using_fallback = False
    
    async def initialize(self):
        """Initialize database with automatic fallback"""
        try:
            # Try primary database first
            self.adapter = create_database_adapter(self.primary_config)
            await self.adapter.initialize()
            self.using_fallback = False
            logger.info(f"✅ Primary database initialized: {self.primary_config.type}")
            
        except Exception as e:
            logger.warning(f"⚠️ Primary database failed: {e}")
            
            if self.fallback_config:
                try:
                    # Fall back to secondary database
                    if self.adapter:
                        await self.adapter.close()
                    
                    self.adapter = create_database_adapter(self.fallback_config)
                    await self.adapter.initialize()
                    self.using_fallback = True
                    logger.info(f"✅ Fallback database initialized: {self.fallback_config.type}")
                    
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback database also failed: {fallback_error}")
                    raise ConnectionError("Both primary and fallback databases failed")
            else:
                raise ConnectionError(f"Primary database failed and no fallback configured: {e}")
    
    async def close(self):
        """Close database connection"""
        if self.adapter:
            await self.adapter.close()
            self.adapter = None
    
    async def health_check(self) -> dict:
        """Check database health and return status"""
        if not self.adapter:
            return {"healthy": False, "error": "No database adapter"}
        
        try:
            healthy = await self.adapter.health_check()
            return {
                "healthy": healthy,
                "type": self.adapter.config.type,
                "using_fallback": self.using_fallback
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def get_adapter(self) -> DatabaseAdapter:
        """Get current database adapter"""
        if not self.adapter:
            raise RuntimeError("Database manager not initialized")
        return self.adapter