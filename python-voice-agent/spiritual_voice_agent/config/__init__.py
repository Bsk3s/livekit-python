"""
Configuration module for Spiritual Voice Agent

Provides environment-aware configuration management with secure defaults.
"""

from .environment import (
    get_config,
    get_config_manager,
    EnvironmentConfig,
    DatabaseConfig,
    ServerConfig,
    SecurityConfig,
    ServicesConfig,
    MonitoringConfig,
    ConfigurationError
)

__all__ = [
    'get_config',
    'get_config_manager', 
    'EnvironmentConfig',
    'DatabaseConfig',
    'ServerConfig',
    'SecurityConfig',
    'ServicesConfig',
    'MonitoringConfig',
    'ConfigurationError'
]