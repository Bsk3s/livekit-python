from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from ..services.monitoring import get_health_service, get_prometheus_metrics, get_uptime_monitor
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """Basic health check endpoint for load balancers"""
    try:
        health_service = get_health_service()
        system_health = await health_service.get_full_health_check()
        
        # Return simple status for load balancers
        if system_health.status.value == "healthy":
            return {"status": "healthy", "timestamp": system_health.timestamp}
        else:
            # Return 503 for unhealthy status
            raise HTTPException(status_code=503, detail={
                "status": system_health.status.value,
                "timestamp": system_health.timestamp
            })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=503, detail={"status": "error", "error": str(e)})


@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with full system status"""
    try:
        health_service = get_health_service()
        system_health = await health_service.get_full_health_check()
        return system_health.to_dict()
    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/health/component/{component_name}")
async def component_health(component_name: str):
    """Get health status for a specific component"""
    try:
        health_service = get_health_service()
        system_health = await health_service.get_full_health_check()
        
        # Find the requested component
        for component in system_health.components:
            if component.name == component_name:
                return {
                    "name": component.name,
                    "status": component.status.value,
                    "response_time_ms": component.response_time_ms,
                    "message": component.message,
                    "details": component.details,
                    "last_check": component.last_check
                }
        
        raise HTTPException(status_code=404, detail=f"Component '{component_name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component health check error: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    try:
        prometheus = get_prometheus_metrics()
        metrics_text = prometheus.get_metrics_text()
        content_type = prometheus.get_content_type()
        
        return Response(content=metrics_text, media_type=content_type)
    except Exception as e:
        logger.error(f"Metrics endpoint error: {e}")
        return Response(content=f"# Error generating metrics: {e}\n", media_type="text/plain")


@router.get("/uptime")
async def uptime_status():
    """Current uptime status for all monitored endpoints"""
    try:
        uptime_monitor = get_uptime_monitor()
        return uptime_monitor.get_current_status()
    except Exception as e:
        logger.error(f"Uptime status error: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/uptime/stats")
async def uptime_statistics(hours: int = 24):
    """Uptime statistics for specified time period"""
    try:
        if hours < 1 or hours > 168:  # Max 1 week
            raise HTTPException(status_code=400, detail="Hours must be between 1 and 168")
        
        uptime_monitor = get_uptime_monitor()
        stats = uptime_monitor.get_uptime_stats(hours)
        overall = uptime_monitor.get_overall_uptime(hours)
        
        return {
            "overall": overall,
            "by_check": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Uptime statistics error: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
