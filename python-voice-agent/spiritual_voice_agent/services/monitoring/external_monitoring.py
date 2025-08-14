"""
External Monitoring Service Integration

Integrates with external monitoring services like DataDog, New Relic, 
and custom webhook endpoints for comprehensive production monitoring.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict

from ...config.environment import get_config

logger = logging.getLogger(__name__)


class MonitoringProvider(Enum):
    """Supported external monitoring providers"""
    DATADOG = "datadog"
    NEW_RELIC = "new_relic"
    WEBHOOK = "webhook"
    PROMETHEUS_PUSHGATEWAY = "prometheus_pushgateway"


@dataclass
class MonitoringEvent:
    """Event to send to external monitoring services"""
    timestamp: str
    event_type: str  # 'metric', 'alert', 'log', 'health_check'
    source: str
    level: str  # 'info', 'warning', 'error', 'critical'
    message: str
    data: Dict[str, Any]
    tags: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExternalMonitoringService:
    """
    External monitoring service integration
    
    Sends metrics, alerts, and health data to external monitoring platforms
    for comprehensive production observability and alerting.
    """
    
    def __init__(self):
        self.config = get_config()
        self.enabled_providers = self._detect_enabled_providers()
        self.session: Optional[aiohttp.ClientSession] = None
        
        if self.enabled_providers:
            logger.info(f"📡 External monitoring enabled: {list(self.enabled_providers.keys())}")
        else:
            logger.info("📡 No external monitoring providers configured")
    
    def _detect_enabled_providers(self) -> Dict[MonitoringProvider, Dict[str, Any]]:
        """Detect which monitoring providers are configured"""
        providers = {}
        
        # Check for DataDog configuration
        datadog_api_key = getattr(self.config.api_keys, 'datadog_api_key', None)
        if datadog_api_key:
            providers[MonitoringProvider.DATADOG] = {
                'api_key': datadog_api_key,
                'site': getattr(self.config.api_keys, 'datadog_site', 'datadoghq.com')
            }
        
        # Check for New Relic configuration
        newrelic_license_key = getattr(self.config.api_keys, 'newrelic_license_key', None)
        if newrelic_license_key:
            providers[MonitoringProvider.NEW_RELIC] = {
                'license_key': newrelic_license_key
            }
        
        # Check for webhook configuration
        webhook_url = getattr(self.config.api_keys, 'monitoring_webhook_url', None)
        if webhook_url:
            providers[MonitoringProvider.WEBHOOK] = {
                'url': webhook_url,
                'secret': getattr(self.config.api_keys, 'monitoring_webhook_secret', None)
            }
        
        # Check for Prometheus Push Gateway
        pushgateway_url = getattr(self.config.api_keys, 'prometheus_pushgateway_url', None)
        if pushgateway_url:
            providers[MonitoringProvider.PROMETHEUS_PUSHGATEWAY] = {
                'url': pushgateway_url
            }
        
        return providers
    
    async def initialize(self):
        """Initialize HTTP session for external API calls"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send_event(self, event: MonitoringEvent):
        """Send event to all configured monitoring providers"""
        if not self.enabled_providers:
            return
        
        await self.initialize()
        
        # Send to all enabled providers concurrently
        tasks = []
        for provider, config in self.enabled_providers.items():
            task = self._send_to_provider(provider, config, event)
            tasks.append(task)
        
        # Execute all sends concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    provider = list(self.enabled_providers.keys())[i]
                    logger.error(f"❌ Failed to send event to {provider.value}: {result}")
    
    async def _send_to_provider(self, provider: MonitoringProvider, config: Dict[str, Any], event: MonitoringEvent):
        """Send event to specific monitoring provider"""
        try:
            if provider == MonitoringProvider.DATADOG:
                await self._send_to_datadog(config, event)
            elif provider == MonitoringProvider.NEW_RELIC:
                await self._send_to_newrelic(config, event)
            elif provider == MonitoringProvider.WEBHOOK:
                await self._send_to_webhook(config, event)
            elif provider == MonitoringProvider.PROMETHEUS_PUSHGATEWAY:
                await self._send_to_prometheus_pushgateway(config, event)
            else:
                logger.warning(f"⚠️ Unknown monitoring provider: {provider}")
                
        except Exception as e:
            logger.error(f"❌ Error sending to {provider.value}: {e}")
            raise
    
    async def _send_to_datadog(self, config: Dict[str, Any], event: MonitoringEvent):
        """Send event to DataDog"""
        api_key = config['api_key']
        site = config['site']
        
        # DataDog Events API
        url = f"https://api.{site}/api/v1/events"
        
        headers = {
            'DD-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        # Convert event to DataDog format
        datadog_event = {
            'title': f"Spiritual Voice Agent - {event.event_type}",
            'text': event.message,
            'date_happened': int(datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')).timestamp()),
            'priority': 'low' if event.level == 'info' else 'normal',
            'alert_type': {
                'info': 'info',
                'warning': 'warning', 
                'error': 'error',
                'critical': 'error'
            }.get(event.level, 'info'),
            'source_type_name': event.source,
            'tags': [f"{k}:{v}" for k, v in event.tags.items()]
        }
        
        async with self.session.post(url, headers=headers, json=datadog_event) as response:
            if response.status == 202:
                logger.debug(f"✅ Event sent to DataDog: {event.event_type}")
            else:
                error_text = await response.text()
                raise Exception(f"DataDog API error {response.status}: {error_text}")
    
    async def _send_to_newrelic(self, config: Dict[str, Any], event: MonitoringEvent):
        """Send event to New Relic"""
        license_key = config['license_key']
        
        # New Relic Events API
        url = "https://insights-collector.newrelic.com/v1/accounts/YOUR_ACCOUNT_ID/events"
        
        headers = {
            'X-License-Key': license_key,
            'Content-Type': 'application/json'
        }
        
        # Convert event to New Relic format
        newrelic_event = {
            'eventType': 'SpiritualVoiceAgent',
            'timestamp': int(datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')).timestamp()),
            'level': event.level,
            'source': event.source,
            'message': event.message,
            'event_type': event.event_type,
            **event.tags,
            **event.data
        }
        
        async with self.session.post(url, headers=headers, json=newrelic_event) as response:
            if response.status == 200:
                logger.debug(f"✅ Event sent to New Relic: {event.event_type}")
            else:
                error_text = await response.text()
                raise Exception(f"New Relic API error {response.status}: {error_text}")
    
    async def _send_to_webhook(self, config: Dict[str, Any], event: MonitoringEvent):
        """Send event to custom webhook"""
        webhook_url = config['url']
        secret = config.get('secret')
        
        headers = {'Content-Type': 'application/json'}
        
        # Add authentication if secret is provided
        if secret:
            headers['Authorization'] = f"Bearer {secret}"
        
        # Send full event data
        payload = {
            'service': 'spiritual_voice_agent',
            'environment': self.config.environment,
            'event': event.to_dict()
        }
        
        async with self.session.post(webhook_url, headers=headers, json=payload) as response:
            if 200 <= response.status < 300:
                logger.debug(f"✅ Event sent to webhook: {event.event_type}")
            else:
                error_text = await response.text()
                raise Exception(f"Webhook error {response.status}: {error_text}")
    
    async def _send_to_prometheus_pushgateway(self, config: Dict[str, Any], event: MonitoringEvent):
        """Send metrics to Prometheus Push Gateway"""
        pushgateway_url = config['url']
        
        # Only send metric events to Prometheus
        if event.event_type != 'metric':
            return
        
        # Convert event data to Prometheus format
        job = event.tags.get('job', 'spiritual_voice_agent')
        instance = event.tags.get('instance', 'default')
        
        url = f"{pushgateway_url}/metrics/job/{job}/instance/{instance}"
        
        # Build Prometheus metrics format
        metrics_lines = []
        for key, value in event.data.items():
            if isinstance(value, (int, float)):
                metric_name = f"spiritual_voice_agent_{key}"
                labels = ",".join([f'{k}="{v}"' for k, v in event.tags.items() if k not in ['job', 'instance']])
                if labels:
                    metric_line = f"{metric_name}{{{labels}}} {value}"
                else:
                    metric_line = f"{metric_name} {value}"
                metrics_lines.append(metric_line)
        
        if not metrics_lines:
            return
        
        payload = "\n".join(metrics_lines)
        
        headers = {'Content-Type': 'text/plain'}
        
        async with self.session.post(url, headers=headers, data=payload) as response:
            if response.status == 200:
                logger.debug(f"✅ Metrics sent to Prometheus Push Gateway")
            else:
                error_text = await response.text()
                raise Exception(f"Prometheus Push Gateway error {response.status}: {error_text}")
    
    async def send_health_check(self, component: str, status: str, response_time_ms: float, details: Optional[Dict[str, Any]] = None):
        """Send health check result to external monitoring"""
        event = MonitoringEvent(
            timestamp=datetime.now().isoformat(),
            event_type='health_check',
            source='health_service',
            level='info' if status == 'healthy' else 'warning' if status == 'warning' else 'error',
            message=f"Health check for {component}: {status}",
            data={
                'component': component,
                'status': status,
                'response_time_ms': response_time_ms,
                **(details or {})
            },
            tags={
                'component': component,
                'environment': self.config.environment,
                'service': 'spiritual_voice_agent'
            }
        )
        
        await self.send_event(event)
    
    async def send_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Send custom metric to external monitoring"""
        event = MonitoringEvent(
            timestamp=datetime.now().isoformat(),
            event_type='metric',
            source='metrics_service',
            level='info',
            message=f"Metric: {metric_name} = {value}",
            data={
                metric_name: value
            },
            tags={
                'environment': self.config.environment,
                'service': 'spiritual_voice_agent',
                **(tags or {})
            }
        )
        
        await self.send_event(event)
    
    async def send_alert(self, alert_type: str, level: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Send alert to external monitoring"""
        event = MonitoringEvent(
            timestamp=datetime.now().isoformat(),
            event_type='alert',
            source='alerting_service',
            level=level,
            message=message,
            data={
                'alert_type': alert_type,
                **(details or {})
            },
            tags={
                'alert_type': alert_type,
                'environment': self.config.environment,
                'service': 'spiritual_voice_agent'
            }
        )
        
        await self.send_event(event)


# Global external monitoring service
_external_monitoring: Optional[ExternalMonitoringService] = None

def get_external_monitoring() -> ExternalMonitoringService:
    """Get global external monitoring service"""
    global _external_monitoring
    if _external_monitoring is None:
        _external_monitoring = ExternalMonitoringService()
    return _external_monitoring