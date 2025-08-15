"""
System Health Monitoring for Voice AI Dashboard
==============================================

Monitors service health, uptime, response times, and system status
for the voice AI dashboard health monitoring component.
"""

import asyncio
import aiohttp
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import psutil

logger = logging.getLogger(__name__)


@dataclass
class ServiceHealth:
    """Health status for a single service."""
    service: str
    status: str  # "healthy", "warning", "critical"
    uptime: float  # Percentage
    response_time: float  # milliseconds
    port: Optional[int] = None
    last_check: str = ""
    error_message: str = ""


@dataclass
class SystemStatus:
    """Overall system health status."""
    overall_status: str
    services: List[ServiceHealth]
    system_metrics: Dict[str, float]
    last_updated: str


class SystemHealthMonitor:
    """
    Monitors health of all voice AI system components.
    
    Services monitored:
    - Main API (FastAPI server)
    - Kokoro TTS server
    - LiveKit connection
    - Database connection
    - System resources (CPU, Memory, Disk)
    """
    
    def __init__(self):
        self.services = {
            "Main API": {
                "url": "http://localhost:10000/health",
                "port": 10000,
                "expected_response_time": 200  # ms
            },
            "Kokoro TTS": {
                "url": "http://localhost:8001/health",
                "port": 8001,
                "expected_response_time": 300  # ms
            },
            "LiveKit Connection": {
                "url": None,  # Special handling for LiveKit
                "port": None,
                "expected_response_time": 100  # ms
            }
        }
        
        self.health_history: Dict[str, List[ServiceHealth]] = {}
        self.uptime_tracking: Dict[str, Dict] = {}
        
        # Initialize uptime tracking
        for service_name in self.services.keys():
            self.uptime_tracking[service_name] = {
                "start_time": time.time(),
                "total_checks": 0,
                "successful_checks": 0,
                "last_failure": None
            }
    
    async def check_service_health(self, service_name: str, config: Dict) -> ServiceHealth:
        """Check health of a single service."""
        start_time = time.time()
        
        try:
            if service_name == "LiveKit Connection":
                # Special handling for LiveKit - check environment and connectivity
                status, response_time = await self._check_livekit_health()
            else:
                # HTTP health check
                status, response_time = await self._check_http_health(config["url"])
            
            # Update uptime tracking
            self.uptime_tracking[service_name]["total_checks"] += 1
            if status == "healthy":
                self.uptime_tracking[service_name]["successful_checks"] += 1
            else:
                self.uptime_tracking[service_name]["last_failure"] = time.time()
            
            # Calculate uptime percentage
            tracking = self.uptime_tracking[service_name]
            uptime_percentage = (tracking["successful_checks"] / tracking["total_checks"]) * 100
            
            service_health = ServiceHealth(
                service=service_name,
                status=status,
                uptime=round(uptime_percentage, 1),
                response_time=round(response_time, 0),
                port=config.get("port"),
                last_check=datetime.now().isoformat(),
                error_message=""
            )
            
            # Add to history
            if service_name not in self.health_history:
                self.health_history[service_name] = []
            
            self.health_history[service_name].append(service_health)
            
            # Keep only last 100 checks per service
            if len(self.health_history[service_name]) > 100:
                self.health_history[service_name] = self.health_history[service_name][-100:]
            
            return service_health
            
        except Exception as e:
            logger.error(f"❌ Error checking {service_name} health: {e}")
            
            # Record failed check
            self.uptime_tracking[service_name]["total_checks"] += 1
            self.uptime_tracking[service_name]["last_failure"] = time.time()
            
            tracking = self.uptime_tracking[service_name]
            uptime_percentage = (tracking["successful_checks"] / tracking["total_checks"]) * 100
            
            return ServiceHealth(
                service=service_name,
                status="critical",
                uptime=round(uptime_percentage, 1),
                response_time=0,
                port=config.get("port"),
                last_check=datetime.now().isoformat(),
                error_message=str(e)
            )
    
    async def _check_http_health(self, url: str) -> Tuple[str, float]:
        """Check HTTP service health."""
        start_time = time.time()
        
        try:
            timeout = aiohttp.ClientTimeout(total=5)  # 5 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response_time = (time.time() - start_time) * 1000  # Convert to ms
                    
                    if response.status == 200:
                        if response_time < 500:
                            return "healthy", response_time
                        elif response_time < 1000:
                            return "warning", response_time
                        else:
                            return "critical", response_time
                    else:
                        return "critical", response_time
                        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return "critical", response_time
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return "critical", response_time
    
    async def _check_livekit_health(self) -> Tuple[str, float]:
        """Check LiveKit connection health."""
        start_time = time.time()
        
        try:
            # Check if LiveKit environment variables are set
            import os
            livekit_url = os.getenv("LIVEKIT_URL")
            livekit_key = os.getenv("LIVEKIT_API_KEY")
            
            if not livekit_url or not livekit_key:
                return "warning", 50  # Missing config but not critical
            
            # Simple connectivity check - for now just check if variables exist
            # In production, you'd want to actually test the connection
            response_time = (time.time() - start_time) * 1000
            
            # Check if agent process is running
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'simple_working_agent' in cmdline and 'main.py' in cmdline:
                        return "healthy", response_time
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Agent not running
            return "warning", response_time
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return "critical", response_time
    
    async def get_system_metrics(self) -> Dict[str, float]:
        """Get system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network stats (simplified)
            network = psutil.net_io_counters()
            network_sent_mb = network.bytes_sent / (1024 * 1024)
            network_recv_mb = network.bytes_recv / (1024 * 1024)
            
            return {
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory_percent, 1),
                "disk_percent": round(disk_percent, 1),
                "network_sent_mb": round(network_sent_mb, 1),
                "network_recv_mb": round(network_recv_mb, 1)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting system metrics: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0,
                "network_sent_mb": 0,
                "network_recv_mb": 0
            }
    
    async def get_full_system_status(self) -> SystemStatus:
        """Get complete system health status."""
        
        # Check all services
        service_healths = []
        for service_name, config in self.services.items():
            health = await self.check_service_health(service_name, config)
            service_healths.append(health)
        
        # Get system metrics
        system_metrics = await self.get_system_metrics()
        
        # Determine overall status
        statuses = [s.status for s in service_healths]
        if "critical" in statuses:
            overall_status = "critical"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return SystemStatus(
            overall_status=overall_status,
            services=service_healths,
            system_metrics=system_metrics,
            last_updated=datetime.now().isoformat()
        )
    
    async def get_service_uptime_report(self, service_name: str, hours: int = 24) -> Dict:
        """Get detailed uptime report for a service."""
        if service_name not in self.health_history:
            return {"error": f"No history for service {service_name}"}
        
        # Get history for specified time period
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_history = [
            h for h in self.health_history[service_name]
            if datetime.fromisoformat(h.last_check) > cutoff_time
        ]
        
        if not recent_history:
            return {"error": f"No recent history for {service_name}"}
        
        # Calculate statistics
        healthy_checks = len([h for h in recent_history if h.status == "healthy"])
        total_checks = len(recent_history)
        uptime_percentage = (healthy_checks / total_checks) * 100
        
        response_times = [h.response_time for h in recent_history if h.response_time > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "service": service_name,
            "time_period_hours": hours,
            "total_checks": total_checks,
            "healthy_checks": healthy_checks,
            "uptime_percentage": round(uptime_percentage, 2),
            "avg_response_time": round(avg_response_time, 2),
            "current_status": recent_history[-1].status if recent_history else "unknown"
        }


# Singleton health monitor
_health_monitor: Optional[SystemHealthMonitor] = None


def get_health_monitor() -> SystemHealthMonitor:
    """Get the global health monitor instance."""
    global _health_monitor
    
    if not _health_monitor:
        _health_monitor = SystemHealthMonitor()
    
    return _health_monitor


# Convenience functions
async def get_system_health() -> SystemStatus:
    """Get complete system health status."""
    monitor = get_health_monitor()
    return await monitor.get_full_system_status()


async def check_service(service_name: str) -> ServiceHealth:
    """Check health of a specific service."""
    monitor = get_health_monitor()
    config = monitor.services.get(service_name, {})
    return await monitor.check_service_health(service_name, config)