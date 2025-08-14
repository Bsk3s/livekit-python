"""
Alerting Service

Provides intelligent alerting for production voice agent monitoring with
configurable rules, notification channels, and alert suppression.
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from .external_monitoring import get_external_monitoring
from .health_service import get_health_service, HealthStatus

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Available notification channels"""
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    WEBHOOK = "webhook"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    description: str
    condition: Callable[[Dict[str, Any]], bool]
    level: AlertLevel
    channels: List[NotificationChannel]
    cooldown_minutes: int = 30
    max_alerts_per_hour: int = 10
    enabled: bool = True


@dataclass
class Alert:
    """Alert instance"""
    id: str
    rule_name: str
    level: AlertLevel
    message: str
    details: Dict[str, Any]
    timestamp: str
    resolved: bool = False
    resolved_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AlertingService:
    """
    Production alerting service
    
    Monitors system health and performance metrics, triggering alerts
    when thresholds are exceeded. Includes intelligent alert suppression,
    escalation, and multiple notification channels.
    """
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.last_notifications: Dict[str, float] = {}  # rule_name -> timestamp
        self.notification_counts: Dict[str, int] = {}  # rule_name -> count in current hour
        
        # Initialize default alert rules
        self._setup_default_rules()
        
        # Start background monitoring
        self._monitoring_task = None
        self._running = False
        self.start_monitoring()
        
        logger.info("🚨 Alerting service initialized with {} rules".format(len(self.rules)))
    
    def _setup_default_rules(self):
        """Setup default alert rules for voice agent monitoring"""
        
        # Database health alerts
        self.add_rule(AlertRule(
            name="database_down",
            description="Database is not responding",
            condition=lambda data: data.get('database_status') == 'critical',
            level=AlertLevel.CRITICAL,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SLACK],
            cooldown_minutes=5,
            max_alerts_per_hour=20
        ))
        
        # High latency alerts
        self.add_rule(AlertRule(
            name="high_voice_latency",
            description="Voice processing latency is high",
            condition=lambda data: data.get('avg_latency_ms', 0) > 3000,
            level=AlertLevel.WARNING,
            channels=[NotificationChannel.SLACK],
            cooldown_minutes=15
        ))
        
        # Critical latency alerts
        self.add_rule(AlertRule(
            name="critical_voice_latency", 
            description="Voice processing latency is critically high",
            condition=lambda data: data.get('avg_latency_ms', 0) > 8000,
            level=AlertLevel.CRITICAL,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SLACK],
            cooldown_minutes=10
        ))
        
        # System resource alerts
        self.add_rule(AlertRule(
            name="high_memory_usage",
            description="System memory usage is high",
            condition=lambda data: data.get('memory_percent', 0) > 85,
            level=AlertLevel.WARNING,
            channels=[NotificationChannel.SLACK],
            cooldown_minutes=30
        ))
        
        self.add_rule(AlertRule(
            name="critical_memory_usage",
            description="System memory usage is critically high", 
            condition=lambda data: data.get('memory_percent', 0) > 95,
            level=AlertLevel.CRITICAL,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SLACK],
            cooldown_minutes=15
        ))
        
        self.add_rule(AlertRule(
            name="high_cpu_usage",
            description="System CPU usage is high",
            condition=lambda data: data.get('cpu_percent', 0) > 80,
            level=AlertLevel.WARNING,
            channels=[NotificationChannel.SLACK],
            cooldown_minutes=20
        ))
        
        self.add_rule(AlertRule(
            name="low_disk_space",
            description="System disk space is low",
            condition=lambda data: data.get('disk_percent', 0) > 90,
            level=AlertLevel.CRITICAL,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SLACK],
            cooldown_minutes=60
        ))
        
        # External service alerts
        self.add_rule(AlertRule(
            name="kokoro_tts_down",
            description="Kokoro TTS service is not responding",
            condition=lambda data: data.get('kokoro_status') == 'critical',
            level=AlertLevel.CRITICAL,
            channels=[NotificationChannel.PAGERDUTY, NotificationChannel.SLACK],
            cooldown_minutes=5
        ))
        
        self.add_rule(AlertRule(
            name="openai_api_errors",
            description="OpenAI API is experiencing errors",
            condition=lambda data: data.get('openai_status') == 'critical',
            level=AlertLevel.WARNING,
            channels=[NotificationChannel.SLACK],
            cooldown_minutes=15
        ))
        
        # Business metric alerts
        self.add_rule(AlertRule(
            name="no_conversations",
            description="No conversations processed in the last hour",
            condition=lambda data: data.get('conversations_last_hour', 0) == 0 and data.get('uptime_hours', 0) > 1,
            level=AlertLevel.WARNING,
            channels=[NotificationChannel.SLACK],
            cooldown_minutes=60
        ))
    
    def add_rule(self, rule: AlertRule):
        """Add new alert rule"""
        self.rules.append(rule)
        logger.info(f"📋 Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove alert rule by name"""
        self.rules = [rule for rule in self.rules if rule.name != rule_name]
        logger.info(f"🗑️ Removed alert rule: {rule_name}")
    
    def start_monitoring(self):
        """Start background monitoring task"""
        if self._monitoring_task and not self._monitoring_task.done():
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("🔍 Alert monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
        logger.info("🛑 Alert monitoring stopped")
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                await self._check_all_rules()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in alert monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_all_rules(self):
        """Check all alert rules against current system state"""
        try:
            # Get current system data
            system_data = await self._collect_system_data()
            
            # Check each rule
            for rule in self.rules:
                if not rule.enabled:
                    continue
                
                try:
                    if rule.condition(system_data):
                        await self._trigger_alert(rule, system_data)
                    else:
                        await self._resolve_alert(rule.name)
                except Exception as e:
                    logger.error(f"❌ Error checking rule {rule.name}: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error collecting system data for alerts: {e}")
    
    async def _collect_system_data(self) -> Dict[str, Any]:
        """Collect current system data for alert evaluation"""
        try:
            health_service = get_health_service()
            system_health = await health_service.get_full_health_check()
            
            # Extract key metrics for alert evaluation
            data = {
                'uptime_hours': system_health.uptime_seconds / 3600,
                'avg_latency_ms': 0,  # Will be filled from performance data
                'conversations_last_hour': 0,  # Will be filled from metrics
            }
            
            # Add component statuses
            for component in system_health.components:
                status_key = f"{component.name}_status"
                data[status_key] = component.status.value
                
                # Extract specific metrics
                if component.details:
                    if component.name == "system_resources":
                        data.update({
                            'cpu_percent': component.details.get('cpu_percent', 0),
                            'memory_percent': component.details.get('memory_percent', 0),
                            'disk_percent': component.details.get('disk_percent', 0)
                        })
                    elif component.name == "application_performance":
                        data['avg_latency_ms'] = component.details.get('avg_latency_ms', 0)
            
            # Add system resource data
            data.update({
                'memory_percent': system_health.memory_usage.get('percent', 0),
                'disk_percent': system_health.disk_usage.get('percent', 0)
            })
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Error collecting system data: {e}")
            return {}
    
    async def _trigger_alert(self, rule: AlertRule, system_data: Dict[str, Any]):
        """Trigger an alert if conditions are met"""
        current_time = time.time()
        
        # Check cooldown period
        last_notification = self.last_notifications.get(rule.name, 0)
        cooldown_seconds = rule.cooldown_minutes * 60
        
        if current_time - last_notification < cooldown_seconds:
            return  # Still in cooldown
        
        # Check rate limiting
        current_hour = int(current_time // 3600)
        count_key = f"{rule.name}_{current_hour}"
        current_count = self.notification_counts.get(count_key, 0)
        
        if current_count >= rule.max_alerts_per_hour:
            return  # Rate limit exceeded
        
        # Create alert
        alert_id = f"{rule.name}_{int(current_time)}"
        alert = Alert(
            id=alert_id,
            rule_name=rule.name,
            level=rule.level,
            message=f"{rule.description} - {rule.name}",
            details=system_data,
            timestamp=datetime.now().isoformat()
        )
        
        # Store alert
        self.active_alerts[rule.name] = alert
        self.alert_history.append(alert)
        
        # Update counters
        self.last_notifications[rule.name] = current_time
        self.notification_counts[count_key] = current_count + 1
        
        # Send notifications
        await self._send_notifications(alert, rule.channels)
        
        # Send to external monitoring
        external_monitoring = get_external_monitoring()
        await external_monitoring.send_alert(
            alert_type=rule.name,
            level=rule.level.value,
            message=alert.message,
            details=alert.details
        )
        
        logger.warning(f"🚨 Alert triggered: {rule.name} - {rule.description}")
    
    async def _resolve_alert(self, rule_name: str):
        """Resolve an active alert"""
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            alert.resolved = True
            alert.resolved_at = datetime.now().isoformat()
            
            del self.active_alerts[rule_name]
            
            logger.info(f"✅ Alert resolved: {rule_name}")
    
    async def _send_notifications(self, alert: Alert, channels: List[NotificationChannel]):
        """Send alert notifications to configured channels"""
        # For now, log the alert. In a real implementation, this would
        # integrate with actual notification services
        
        channel_names = [channel.value for channel in channels]
        logger.warning(f"🚨 ALERT [{alert.level.value.upper()}]: {alert.message}")
        logger.warning(f"📢 Would notify channels: {', '.join(channel_names)}")
        
        # Here you would integrate with:
        # - Slack API for Slack notifications
        # - PagerDuty API for incident creation
        # - Email service for email alerts
        # - SMS service for text alerts
        # - Custom webhooks
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        return [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert.timestamp) > cutoff
        ]
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alerting statistics"""
        active_count = len(self.active_alerts)
        total_rules = len(self.rules)
        enabled_rules = len([rule for rule in self.rules if rule.enabled])
        
        # Count alerts by level in last 24 hours
        recent_alerts = self.get_alert_history(24)
        level_counts = {
            'info': len([a for a in recent_alerts if a.level == AlertLevel.INFO]),
            'warning': len([a for a in recent_alerts if a.level == AlertLevel.WARNING]),
            'critical': len([a for a in recent_alerts if a.level == AlertLevel.CRITICAL])
        }
        
        return {
            'active_alerts': active_count,
            'total_rules': total_rules,
            'enabled_rules': enabled_rules,
            'alerts_last_24h': len(recent_alerts),
            'alerts_by_level': level_counts
        }


# Global alerting service
_alerting_service: Optional[AlertingService] = None

def get_alerting_service() -> AlertingService:
    """Get global alerting service"""
    global _alerting_service
    if _alerting_service is None:
        _alerting_service = AlertingService()
    return _alerting_service