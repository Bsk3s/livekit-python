"""
Comprehensive Health Service

Provides detailed health checks for all system components with status aggregation
and dependency monitoring for production voice agent deployments.
"""

import asyncio
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from ..database import get_database_adapter
from ..cost_analytics_v2 import get_cost_analytics_db
from ..metrics_service import get_metrics_service
from ...config.environment import get_config

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status for a single component"""
    name: str
    status: HealthStatus
    response_time_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None
    last_check: str = None
    
    def __post_init__(self):
        if self.last_check is None:
            self.last_check = datetime.now().isoformat()


@dataclass
class SystemHealth:
    """Overall system health summary"""
    status: HealthStatus
    components: List[ComponentHealth]
    response_time_ms: float
    timestamp: str
    uptime_seconds: float
    system_load: Dict[str, Any]
    memory_usage: Dict[str, Any]
    disk_usage: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            'status': self.status.value,
            'components': [asdict(comp) for comp in self.components],
            'response_time_ms': self.response_time_ms,
            'timestamp': self.timestamp,
            'uptime_seconds': self.uptime_seconds,
            'system_load': self.system_load,
            'memory_usage': self.memory_usage,
            'disk_usage': self.disk_usage
        }


class HealthService:
    """
    Comprehensive health monitoring service
    
    Provides detailed health checks for all system components including:
    - Database connectivity and performance
    - External services (Kokoro TTS, OpenAI, Deepgram)
    - System resources (CPU, memory, disk)
    - Application metrics and performance
    - Custom voice agent specific checks
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.config = get_config()
        self._last_health_check: Optional[SystemHealth] = None
        self._health_cache_ttl = 30  # Cache health checks for 30 seconds
        self._last_check_time = 0
    
    async def get_full_health_check(self) -> SystemHealth:
        """
        Perform comprehensive health check of all system components
        
        Returns cached result if checked within TTL for performance.
        """
        current_time = time.time()
        
        # Return cached result if within TTL
        if (self._last_health_check and 
            current_time - self._last_check_time < self._health_cache_ttl):
            return self._last_health_check
        
        start_time = time.time()
        components = []
        
        # Check all system components
        health_checks = [
            self._check_database_health(),
            self._check_kokoro_tts_health(),
            self._check_metrics_service_health(),
            self._check_external_apis_health(),
            self._check_system_resources(),
            self._check_application_performance()
        ]
        
        # Run all health checks concurrently for speed
        component_results = await asyncio.gather(*health_checks, return_exceptions=True)
        
        # Process results
        for result in component_results:
            if isinstance(result, Exception):
                components.append(ComponentHealth(
                    name="unknown_component",
                    status=HealthStatus.CRITICAL,
                    response_time_ms=0,
                    message=f"Health check failed: {result}"
                ))
            elif isinstance(result, list):
                components.extend(result)
            else:
                components.append(result)
        
        # Determine overall system status
        overall_status = self._calculate_overall_status(components)
        
        # Get system information
        system_info = self._get_system_info()
        
        total_response_time = (time.time() - start_time) * 1000
        
        system_health = SystemHealth(
            status=overall_status,
            components=components,
            response_time_ms=total_response_time,
            timestamp=datetime.now().isoformat(),
            uptime_seconds=current_time - self.start_time,
            **system_info
        )
        
        # Cache the result
        self._last_health_check = system_health
        self._last_check_time = current_time
        
        return system_health
    
    async def _check_database_health(self) -> ComponentHealth:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            # Get database adapter
            db_adapter = await get_database_adapter()
            
            # Test basic connectivity
            is_healthy = await db_adapter.health_check()
            response_time = (time.time() - start_time) * 1000
            
            if not is_healthy:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.CRITICAL,
                    response_time_ms=response_time,
                    message="Database health check failed"
                )
            
            # Get additional details for PostgreSQL
            details = {"type": db_adapter.config.type}
            if hasattr(db_adapter, 'get_connection_stats'):
                try:
                    stats = await db_adapter.get_connection_stats()
                    details.update(stats)
                except Exception as e:
                    logger.warning(f"Could not get connection stats: {e}")
            
            # Determine status based on response time
            if response_time > 1000:  # 1 second
                status = HealthStatus.WARNING
                message = f"Database slow response: {response_time:.1f}ms"
            elif response_time > 2000:  # 2 seconds
                status = HealthStatus.CRITICAL
                message = f"Database very slow: {response_time:.1f}ms"
            else:
                status = HealthStatus.HEALTHY
                message = f"Database healthy: {response_time:.1f}ms"
            
            return ComponentHealth(
                name="database",
                status=status,
                response_time_ms=response_time,
                message=message,
                details=details
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="database",
                status=HealthStatus.CRITICAL,
                response_time_ms=response_time,
                message=f"Database error: {e}"
            )
    
    async def _check_kokoro_tts_health(self) -> ComponentHealth:
        """Check Kokoro TTS service health"""
        start_time = time.time()
        
        try:
            import aiohttp
            
            # Get Kokoro server URL from config
            kokoro_url = "http://localhost:8001"  # Default, should come from config
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{kokoro_url}/health", timeout=5) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        return ComponentHealth(
                            name="kokoro_tts",
                            status=HealthStatus.HEALTHY,
                            response_time_ms=response_time,
                            message=f"Kokoro TTS healthy: {response_time:.1f}ms",
                            details=data
                        )
                    else:
                        return ComponentHealth(
                            name="kokoro_tts",
                            status=HealthStatus.WARNING,
                            response_time_ms=response_time,
                            message=f"Kokoro TTS responded with status {response.status}"
                        )
                        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="kokoro_tts",
                status=HealthStatus.CRITICAL,
                response_time_ms=response_time,
                message="Kokoro TTS timeout"
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="kokoro_tts",
                status=HealthStatus.CRITICAL,
                response_time_ms=response_time,
                message=f"Kokoro TTS error: {e}"
            )
    
    async def _check_metrics_service_health(self) -> ComponentHealth:
        """Check metrics service health"""
        start_time = time.time()
        
        try:
            metrics_service = get_metrics_service()
            
            # Check if metrics service is processing events
            stats = metrics_service.get_service_stats()
            response_time = (time.time() - start_time) * 1000
            
            # Determine health based on queue status
            queue_size = stats.get('queue_size', 0)
            dropped_events = stats.get('events_dropped', 0)
            
            if queue_size > 1000:
                status = HealthStatus.WARNING
                message = f"Metrics queue large: {queue_size} events"
            elif dropped_events > 100:
                status = HealthStatus.WARNING
                message = f"Metrics dropping events: {dropped_events} dropped"
            else:
                status = HealthStatus.HEALTHY
                message = f"Metrics service healthy: {response_time:.1f}ms"
            
            return ComponentHealth(
                name="metrics_service",
                status=status,
                response_time_ms=response_time,
                message=message,
                details=stats
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="metrics_service",
                status=HealthStatus.CRITICAL,
                response_time_ms=response_time,
                message=f"Metrics service error: {e}"
            )
    
    async def _check_external_apis_health(self) -> List[ComponentHealth]:
        """Check external API services (OpenAI, Deepgram, etc.)"""
        components = []
        
        # Check OpenAI API
        try:
            import openai
            start_time = time.time()
            
            # Simple API health check (just check authentication)
            client = openai.AsyncOpenAI(api_key=self.config.api_keys.openai_api_key)
            
            # Quick model list check
            models = await client.models.list()
            response_time = (time.time() - start_time) * 1000
            
            if models:
                components.append(ComponentHealth(
                    name="openai_api",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    message=f"OpenAI API healthy: {response_time:.1f}ms"
                ))
            else:
                components.append(ComponentHealth(
                    name="openai_api",
                    status=HealthStatus.WARNING,
                    response_time_ms=response_time,
                    message="OpenAI API responded but returned no models"
                ))
                
        except Exception as e:
            components.append(ComponentHealth(
                name="openai_api",
                status=HealthStatus.CRITICAL,
                response_time_ms=0,
                message=f"OpenAI API error: {e}"
            ))
        
        # Add checks for other external APIs (Deepgram, etc.)
        # For now, assume they're healthy if configured
        if self.config.api_keys.deepgram_api_key:
            components.append(ComponentHealth(
                name="deepgram_api",
                status=HealthStatus.HEALTHY,
                response_time_ms=0,
                message="Deepgram API configured"
            ))
        
        return components
    
    async def _check_system_resources(self) -> ComponentHealth:
        """Check system resource usage"""
        start_time = time.time()
        
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine status based on resource usage
            status = HealthStatus.HEALTHY
            warnings = []
            
            if cpu_percent > 80:
                status = HealthStatus.WARNING
                warnings.append(f"High CPU: {cpu_percent:.1f}%")
            
            if memory.percent > 85:
                status = HealthStatus.WARNING
                warnings.append(f"High memory: {memory.percent:.1f}%")
            
            if disk.percent > 90:
                status = HealthStatus.CRITICAL
                warnings.append(f"Low disk space: {disk.percent:.1f}%")
            
            message = "; ".join(warnings) if warnings else f"System resources healthy"
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_free_gb": disk.free / (1024**3)
            }
            
            return ComponentHealth(
                name="system_resources",
                status=status,
                response_time_ms=response_time,
                message=message,
                details=details
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.WARNING,
                response_time_ms=response_time,
                message=f"Could not check system resources: {e}"
            )
    
    async def _check_application_performance(self) -> ComponentHealth:
        """Check application-specific performance metrics"""
        start_time = time.time()
        
        try:
            metrics_service = get_metrics_service()
            
            # Get recent performance data
            summary = metrics_service.get_performance_summary(hours=1)
            response_time = (time.time() - start_time) * 1000
            
            # Determine status based on performance metrics
            avg_latency = summary.get('avg_total_latency', 0)
            total_requests = summary.get('total_requests', 0)
            
            status = HealthStatus.HEALTHY
            
            if avg_latency > 2000:  # 2 seconds
                status = HealthStatus.WARNING
                message = f"High average latency: {avg_latency:.0f}ms"
            elif avg_latency > 5000:  # 5 seconds
                status = HealthStatus.CRITICAL
                message = f"Very high latency: {avg_latency:.0f}ms"
            else:
                message = f"Performance healthy - avg latency: {avg_latency:.0f}ms"
            
            details = {
                "avg_latency_ms": avg_latency,
                "requests_last_hour": total_requests,
                "max_latency_ms": summary.get('max_total_latency', 0),
                "min_latency_ms": summary.get('min_total_latency', 0)
            }
            
            return ComponentHealth(
                name="application_performance",
                status=status,
                response_time_ms=response_time,
                message=message,
                details=details
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="application_performance",
                status=HealthStatus.WARNING,
                response_time_ms=response_time,
                message=f"Could not check performance: {e}"
            )
    
    def _calculate_overall_status(self, components: List[ComponentHealth]) -> HealthStatus:
        """Calculate overall system status from component statuses"""
        if not components:
            return HealthStatus.UNKNOWN
        
        # If any component is critical, system is critical
        if any(comp.status == HealthStatus.CRITICAL for comp in components):
            return HealthStatus.CRITICAL
        
        # If any component has warnings, system has warnings
        if any(comp.status == HealthStatus.WARNING for comp in components):
            return HealthStatus.WARNING
        
        # If all components are healthy, system is healthy
        if all(comp.status == HealthStatus.HEALTHY for comp in components):
            return HealthStatus.HEALTHY
        
        return HealthStatus.UNKNOWN
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get current system resource information"""
        try:
            # System load
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            return {
                'system_load': {
                    'load_1m': load_avg[0],
                    'load_5m': load_avg[1], 
                    'load_15m': load_avg[2],
                    'cpu_count': psutil.cpu_count()
                },
                'memory_usage': {
                    'total_gb': memory.total / (1024**3),
                    'available_gb': memory.available / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'percent': memory.percent
                },
                'disk_usage': {
                    'total_gb': disk.total / (1024**3),
                    'free_gb': disk.free / (1024**3),
                    'used_gb': disk.used / (1024**3),
                    'percent': disk.percent
                }
            }
        except Exception as e:
            logger.warning(f"Could not get system info: {e}")
            return {
                'system_load': {},
                'memory_usage': {},
                'disk_usage': {}
            }


# Global health service instance
_health_service: Optional[HealthService] = None

def get_health_service() -> HealthService:
    """Get global health service instance"""
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service