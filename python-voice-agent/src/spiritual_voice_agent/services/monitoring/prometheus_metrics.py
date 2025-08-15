"""
Prometheus Metrics Integration

Provides Prometheus metrics collection for monitoring voice agent performance,
resource usage, and business metrics in production environments.
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
        def time(self): return MockTimer()
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Info:
        def __init__(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
    
    class MockTimer:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    def generate_latest(): return b""
    CONTENT_TYPE_LATEST = "text/plain"

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """
    Prometheus metrics collector for voice agent monitoring
    
    Collects comprehensive metrics for:
    - Voice pipeline performance (latency, throughput)
    - System resources (CPU, memory, disk)
    - Business metrics (conversations, users, costs)
    - Error rates and success metrics
    - External service performance
    """
    
    def __init__(self):
        self.enabled = PROMETHEUS_AVAILABLE
        
        if not self.enabled:
            logger.warning("⚠️ Prometheus client not available - metrics disabled")
            return
        
        logger.info("📊 Initializing Prometheus metrics collection")
        
        # Voice pipeline metrics
        self.voice_requests_total = Counter(
            'voice_requests_total',
            'Total number of voice requests processed',
            ['character', 'status', 'source']
        )
        
        self.voice_latency_seconds = Histogram(
            'voice_latency_seconds',
            'Voice processing latency in seconds',
            ['component', 'character'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        self.voice_sessions_active = Gauge(
            'voice_sessions_active',
            'Number of active voice sessions'
        )
        
        # System resource metrics
        self.system_cpu_usage = Gauge(
            'system_cpu_usage_percent',
            'System CPU usage percentage'
        )
        
        self.system_memory_usage = Gauge(
            'system_memory_usage_bytes',
            'System memory usage in bytes',
            ['type']  # total, used, available
        )
        
        self.system_disk_usage = Gauge(
            'system_disk_usage_bytes',
            'System disk usage in bytes',
            ['type']  # total, used, free
        )
        
        # Database metrics
        self.database_operations_total = Counter(
            'database_operations_total',
            'Total database operations',
            ['operation', 'status']
        )
        
        self.database_latency_seconds = Histogram(
            'database_latency_seconds',
            'Database operation latency in seconds',
            ['operation'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
        )
        
        self.database_connections = Gauge(
            'database_connections',
            'Database connection pool status',
            ['status']  # active, idle, total
        )
        
        # External service metrics
        self.external_api_requests_total = Counter(
            'external_api_requests_total',
            'External API requests',
            ['service', 'status']
        )
        
        self.external_api_latency_seconds = Histogram(
            'external_api_latency_seconds',
            'External API latency in seconds',
            ['service'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        # Business metrics
        self.conversations_total = Counter(
            'conversations_total',
            'Total conversations completed',
            ['character', 'success']
        )
        
        self.cost_total_usd = Counter(
            'cost_total_usd',
            'Total cost in USD',
            ['component']  # stt, llm, tts
        )
        
        self.users_active = Gauge(
            'users_active',
            'Number of active users',
            ['period']  # hourly, daily
        )
        
        # Health check metrics
        self.health_check_duration_seconds = Histogram(
            'health_check_duration_seconds',
            'Health check duration in seconds',
            ['component']
        )
        
        self.component_health_status = Gauge(
            'component_health_status',
            'Component health status (1=healthy, 0.5=warning, 0=critical)',
            ['component']
        )
        
        # Application info
        self.app_info = Info(
            'spiritual_voice_agent_info',
            'Application information'
        )
        
        # Set application info
        self.app_info.info({
            'version': '1.0.0',
            'environment': 'production',  # Should come from config
            'tts_engine': 'kokoro',
            'llm_provider': 'openai'
        })
        
        logger.info("✅ Prometheus metrics initialized")
    
    def record_voice_request(self, character: str, status: str, source: str = "api"):
        """Record a voice request"""
        if self.enabled:
            self.voice_requests_total.labels(
                character=character,
                status=status,
                source=source
            ).inc()
    
    def record_voice_latency(self, component: str, character: str, latency_seconds: float):
        """Record voice processing latency"""
        if self.enabled:
            self.voice_latency_seconds.labels(
                component=component,
                character=character
            ).observe(latency_seconds)
    
    def set_active_sessions(self, count: int):
        """Set number of active voice sessions"""
        if self.enabled:
            self.voice_sessions_active.set(count)
    
    def update_system_metrics(self, cpu_percent: float, memory_info: Dict[str, float], disk_info: Dict[str, float]):
        """Update system resource metrics"""
        if not self.enabled:
            return
        
        self.system_cpu_usage.set(cpu_percent)
        
        for mem_type, value in memory_info.items():
            self.system_memory_usage.labels(type=mem_type).set(value)
        
        for disk_type, value in disk_info.items():
            self.system_disk_usage.labels(type=disk_type).set(value)
    
    def record_database_operation(self, operation: str, status: str, latency_seconds: float):
        """Record database operation metrics"""
        if not self.enabled:
            return
        
        self.database_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        self.database_latency_seconds.labels(operation=operation).observe(latency_seconds)
    
    def update_database_connections(self, active: int, idle: int, total: int):
        """Update database connection pool metrics"""
        if not self.enabled:
            return
        
        self.database_connections.labels(status="active").set(active)
        self.database_connections.labels(status="idle").set(idle)
        self.database_connections.labels(status="total").set(total)
    
    def record_external_api_call(self, service: str, status: str, latency_seconds: float):
        """Record external API call metrics"""
        if not self.enabled:
            return
        
        self.external_api_requests_total.labels(
            service=service,
            status=status
        ).inc()
        
        self.external_api_latency_seconds.labels(service=service).observe(latency_seconds)
    
    def record_conversation(self, character: str, success: bool):
        """Record completed conversation"""
        if self.enabled:
            self.conversations_total.labels(
                character=character,
                success="success" if success else "failure"
            ).inc()
    
    def record_cost(self, component: str, cost_usd: float):
        """Record cost metrics"""
        if self.enabled:
            self.cost_total_usd.labels(component=component).inc(cost_usd)
    
    def set_active_users(self, hourly_count: int, daily_count: int):
        """Set active user counts"""
        if not self.enabled:
            return
        
        self.users_active.labels(period="hourly").set(hourly_count)
        self.users_active.labels(period="daily").set(daily_count)
    
    def record_health_check(self, component: str, duration_seconds: float, status: str):
        """Record health check metrics"""
        if not self.enabled:
            return
        
        self.health_check_duration_seconds.labels(component=component).observe(duration_seconds)
        
        # Convert status to numeric value
        status_value = {
            "healthy": 1.0,
            "warning": 0.5,
            "critical": 0.0,
            "unknown": -1.0
        }.get(status, -1.0)
        
        self.component_health_status.labels(component=component).set(status_value)
    
    def get_metrics_text(self) -> str:
        """Get Prometheus metrics in text format"""
        if not self.enabled:
            return "# Prometheus metrics not available\n"
        
        return generate_latest().decode('utf-8')
    
    def get_content_type(self) -> str:
        """Get Prometheus metrics content type"""
        return CONTENT_TYPE_LATEST


# Global metrics instance
_prometheus_metrics: Optional[PrometheusMetrics] = None

def get_prometheus_metrics() -> PrometheusMetrics:
    """Get global Prometheus metrics instance"""
    global _prometheus_metrics
    if _prometheus_metrics is None:
        _prometheus_metrics = PrometheusMetrics()
    return _prometheus_metrics


def record_voice_pipeline_metrics(
    character: str,
    total_latency_ms: float,
    stt_latency_ms: Optional[float] = None,
    llm_latency_ms: Optional[float] = None,
    tts_latency_ms: Optional[float] = None,
    success: bool = True
):
    """Convenience function to record voice pipeline metrics"""
    metrics = get_prometheus_metrics()
    
    # Record request
    metrics.record_voice_request(
        character=character,
        status="success" if success else "error",
        source="voice_pipeline"
    )
    
    # Record latencies
    metrics.record_voice_latency("total", character, total_latency_ms / 1000)
    
    if stt_latency_ms is not None:
        metrics.record_voice_latency("stt", character, stt_latency_ms / 1000)
    
    if llm_latency_ms is not None:
        metrics.record_voice_latency("llm", character, llm_latency_ms / 1000)
    
    if tts_latency_ms is not None:
        metrics.record_voice_latency("tts", character, tts_latency_ms / 1000)
    
    # Record conversation
    metrics.record_conversation(character, success)