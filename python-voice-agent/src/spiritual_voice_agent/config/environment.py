"""
Environment Configuration Management for Spiritual Voice Agent

Provides secure, environment-aware configuration with proper defaults
and validation for development, staging, and production environments.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    type: str = "sqlite"  # sqlite or postgresql
    url: Optional[str] = None
    pool_size: int = 10
    max_overflow: int = 20
    sqlite_path: str = "logs/cost_analytics.db"


@dataclass
class ServerConfig:
    """Server configuration settings"""
    host: str = "0.0.0.0"
    port: int = 10000
    workers: int = 1
    log_level: str = "INFO"
    log_format: str = "structured"
    debug_requests: bool = False


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    cors_origins: List[str]
    session_max_duration: int = 120
    session_min_duration: int = 5
    session_default_duration: int = 30
    rate_limit_enabled: bool = False


@dataclass
class ServicesConfig:
    """External services configuration"""
    livekit_api_key: str
    livekit_api_secret: str
    openai_api_key: str
    deepgram_api_key: str
    kokoro_server_url: str = "http://localhost:8001"
    kokoro_voice: str = "adina"
    kokoro_speed: float = 1.1


@dataclass
class MonitoringConfig:
    """Monitoring and metrics configuration"""
    metrics_enabled: bool = True
    cost_tracking_enabled: bool = True
    retention_days: int = 30
    health_check_timeout: int = 30
    shutdown_timeout: int = 30


@dataclass
class EnvironmentConfig:
    """Complete environment configuration"""
    environment: str
    database: DatabaseConfig
    server: ServerConfig
    security: SecurityConfig
    services: ServicesConfig
    monitoring: MonitoringConfig


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class EnvironmentManager:
    """
    Manages environment-specific configuration with secure defaults
    """
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development').lower()
        self._config: Optional[EnvironmentConfig] = None
        
    def get_config(self) -> EnvironmentConfig:
        """Get configuration for current environment"""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def _load_config(self) -> EnvironmentConfig:
        """Load configuration based on environment"""
        logger.info(f"🔧 Loading configuration for environment: {self.environment}")
        
        if self.environment == 'production':
            return self._load_production_config()
        elif self.environment == 'staging':
            return self._load_staging_config()
        else:
            return self._load_development_config()
    
    def _load_development_config(self) -> EnvironmentConfig:
        """Development environment configuration"""
        return EnvironmentConfig(
            environment='development',
            database=DatabaseConfig(
                type='sqlite',
                sqlite_path='logs/dev_cost_analytics.db'
            ),
            server=ServerConfig(
                port=10000,
                log_level='DEBUG',
                debug_requests=True,
                workers=1
            ),
            security=SecurityConfig(
                cors_origins=self._get_development_cors_origins(),
                session_default_duration=15,
                session_max_duration=60
            ),
            services=self._load_services_config(),
            monitoring=MonitoringConfig(
                retention_days=7,
                health_check_timeout=30
            )
        )
    
    def _load_staging_config(self) -> EnvironmentConfig:
        """Staging environment configuration"""
        return EnvironmentConfig(
            environment='staging',
            database=DatabaseConfig(
                type='sqlite',
                sqlite_path='logs/staging_cost_analytics.db'
            ),
            server=ServerConfig(
                port=10000,
                log_level='INFO',
                debug_requests=False,
                workers=2
            ),
            security=SecurityConfig(
                cors_origins=self._get_staging_cors_origins(),
                session_default_duration=30,
                session_max_duration=120
            ),
            services=self._load_services_config(),
            monitoring=MonitoringConfig(
                retention_days=14,
                health_check_timeout=30
            )
        )
    
    def _load_production_config(self) -> EnvironmentConfig:
        """Production environment configuration"""
        return EnvironmentConfig(
            environment='production',
            database=self._get_production_database_config(),
            server=ServerConfig(
                port=int(os.getenv('PORT', 10000)),
                log_level=os.getenv('LOG_LEVEL', 'INFO'),
                debug_requests=False,
                workers=int(os.getenv('WORKERS', 4))
            ),
            security=SecurityConfig(
                cors_origins=self._get_production_cors_origins(),
                session_default_duration=30,
                session_max_duration=120
            ),
            services=self._load_services_config(),
            monitoring=MonitoringConfig(
                retention_days=30,
                health_check_timeout=10,
                shutdown_timeout=45
            )
        )
    
    def _get_development_cors_origins(self) -> List[str]:
        """Development CORS origins - local only"""
        return [
            "http://localhost:3000",
            "http://localhost:19006", 
            "http://127.0.0.1:3000",
            "http://127.0.0.1:19006"
        ]
    
    def _get_staging_cors_origins(self) -> List[str]:
        """Staging CORS origins - development + staging platforms"""
        dev_origins = self._get_development_cors_origins()
        staging_origins = [
            "https://*.up.railway.app",
            "https://*.expo.dev"
        ]
        
        # Add custom staging origins from environment
        extra_origins = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
        extra_origins = [origin.strip() for origin in extra_origins if origin.strip()]
        
        return dev_origins + staging_origins + extra_origins
    
    def _get_production_cors_origins(self) -> List[str]:
        """Production CORS origins - explicit configuration required"""
        cors_env = os.getenv('CORS_ALLOWED_ORIGINS', '').strip()
        
        if not cors_env:
            logger.warning("⚠️ No CORS_ALLOWED_ORIGINS set for production - API will be inaccessible from web")
            return []
        
        origins = [origin.strip() for origin in cors_env.split(',') if origin.strip()]
        logger.info(f"🔒 Production CORS configured for {len(origins)} origins")
        return origins
    
    def _get_production_database_config(self) -> DatabaseConfig:
        """Production database configuration with PostgreSQL support"""
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # PostgreSQL configuration
            return DatabaseConfig(
                type='postgresql',
                url=database_url,
                pool_size=int(os.getenv('DB_POOL_SIZE', 20)),
                max_overflow=int(os.getenv('DB_MAX_OVERFLOW', 40))
            )
        else:
            # Check for individual PostgreSQL settings
            pg_host = os.getenv('POSTGRES_HOST')
            pg_user = os.getenv('POSTGRES_USER')
            pg_password = os.getenv('POSTGRES_PASSWORD')
            pg_db = os.getenv('POSTGRES_DB')
            
            if all([pg_host, pg_user, pg_password, pg_db]):
                # Individual PostgreSQL settings
                return DatabaseConfig(
                    type='postgresql',
                    host=pg_host,
                    port=int(os.getenv('POSTGRES_PORT', 5432)),
                    username=pg_user,
                    password=pg_password,
                    database=pg_db,
                    pool_size=int(os.getenv('DB_POOL_SIZE', 20)),
                    max_overflow=int(os.getenv('DB_MAX_OVERFLOW', 40))
                )
            else:
                # SQLite fallback for production
                logger.warning("⚠️ No PostgreSQL config found, using SQLite in production")
                return DatabaseConfig(
                    type='sqlite',
                    sqlite_path=os.getenv('SQLITE_DB_PATH', '/app/data/cost_analytics.db')
                )
    
    def _load_services_config(self) -> ServicesConfig:
        """Load external services configuration with validation"""
        
        # Required API keys
        required_keys = {
            'LIVEKIT_API_KEY': 'livekit_api_key',
            'LIVEKIT_API_SECRET': 'livekit_api_secret', 
            'OPENAI_API_KEY': 'openai_api_key',
            'DEEPGRAM_API_KEY': 'deepgram_api_key'
        }
        
        config_dict = {}
        missing_keys = []
        
        for env_key, config_key in required_keys.items():
            value = os.getenv(env_key, '').strip()
            if not value:
                missing_keys.append(env_key)
            config_dict[config_key] = value
        
        if missing_keys and self.environment == 'production':
            raise ConfigurationError(f"Missing required environment variables for production: {missing_keys}")
        elif missing_keys:
            logger.warning(f"⚠️ Missing environment variables (using defaults): {missing_keys}")
            # Use placeholder values for development
            for env_key, config_key in required_keys.items():
                if config_key not in config_dict or not config_dict[config_key]:
                    config_dict[config_key] = f"dev_{config_key}"
        
        # Optional service settings
        config_dict.update({
            'kokoro_server_url': os.getenv('KOKORO_SERVER_URL', 'http://localhost:8001'),
            'kokoro_voice': os.getenv('KOKORO_VOICE', 'adina'),
            'kokoro_speed': float(os.getenv('KOKORO_SPEED', 1.1))
        })
        
        return ServicesConfig(**config_dict)
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        config = self.get_config()
        issues = []
        
        # Validate services
        if self.environment == 'production':
            if not config.services.livekit_api_key or config.services.livekit_api_key.startswith('dev_'):
                issues.append("Production requires valid LIVEKIT_API_KEY")
            if not config.services.openai_api_key or config.services.openai_api_key.startswith('dev_'):
                issues.append("Production requires valid OPENAI_API_KEY")
            if not config.security.cors_origins:
                issues.append("Production requires CORS_ALLOWED_ORIGINS configuration")
        
        # Validate database
        if config.database.type == 'postgresql' and not config.database.url:
            issues.append("PostgreSQL requires DATABASE_URL")
        
        return issues
    
    def print_config_summary(self):
        """Print configuration summary for debugging"""
        config = self.get_config()
        
        print(f"\n🔧 Environment Configuration Summary")
        print(f"═══════════════════════════════════")
        print(f"Environment: {config.environment}")
        print(f"Server: {config.server.host}:{config.server.port} ({config.server.workers} workers)")
        print(f"Database: {config.database.type} ({'URL configured' if config.database.url else config.database.sqlite_path})")
        print(f"CORS Origins: {len(config.security.cors_origins)} configured")
        print(f"Monitoring: {'Enabled' if config.monitoring.metrics_enabled else 'Disabled'}")
        print(f"Log Level: {config.server.log_level}")
        
        issues = self.validate_config()
        if issues:
            print(f"\n⚠️ Configuration Issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"\n✅ Configuration validation passed")


# Global configuration manager instance
_config_manager = None

def get_config_manager() -> EnvironmentManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = EnvironmentManager()
    return _config_manager

def get_config() -> EnvironmentConfig:
    """Get current environment configuration"""
    return get_config_manager().get_config()