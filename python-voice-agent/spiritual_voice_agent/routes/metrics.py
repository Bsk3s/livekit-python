from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from spiritual_voice_agent.services.metrics_service import get_metrics_service

router = APIRouter()

@router.get("/metrics", response_class=HTMLResponse)
async def metrics_dashboard():
    """Simple metrics dashboard"""
    metrics_service = get_metrics_service()
    summary = metrics_service.get_performance_summary(hours=1)
    recent_events = metrics_service.get_recent_events(limit=10)
    
    # Format latencies for display
    avg_latency = f"{summary['avg_latency_ms']:.0f}ms" if summary['avg_latency_ms'] > 0 else "No data"
    success_rate = f"{summary['success_rate']*100:.1f}%" if summary['success_rate'] > 0 else "No data"
    
    # Stage breakdown
    stage_breakdown = summary.get('stage_breakdown', {})
    stt_avg = f"{stage_breakdown.get('stt_avg_ms', 0):.0f}ms"
    llm_avg = f"{stage_breakdown.get('llm_avg_ms', 0):.0f}ms"
    tts_avg = f"{stage_breakdown.get('tts_avg_ms', 0):.0f}ms"
    
    # Character performance
    char_perf = summary.get('character_performance', {})
    adina_stats = char_perf.get('adina', {})
    raffa_stats = char_perf.get('raffa', {})
    
    adina_display = f"{adina_stats.get('avg_latency_ms', 0):.0f}ms ({adina_stats.get('requests', 0)} requests)" if adina_stats else "No data"
    raffa_display = f"{raffa_stats.get('avg_latency_ms', 0):.0f}ms ({raffa_stats.get('requests', 0)} requests)" if raffa_stats else "No data"
    
    # Determine status colors
    def get_status_color(latency_ms):
        if latency_ms == 0:
            return "#888888"  # gray for no data
        elif latency_ms < 500:
            return "#10B981"  # green
        elif latency_ms < 1000:
            return "#F59E0B"  # yellow
        elif latency_ms < 1500:
            return "#EF4444"  # red
        else:
            return "#7C2D12"  # dark red
    
    stt_color = get_status_color(stage_breakdown.get('stt_avg_ms', 0))
    llm_color = get_status_color(stage_breakdown.get('llm_avg_ms', 0))
    tts_color = get_status_color(stage_breakdown.get('tts_avg_ms', 0))
    
    # Recent events table
    events_html = ""
    for event in recent_events:
        timestamp = event['timestamp'][:19].replace('T', ' ')  # Format timestamp
        status_icon = "✅" if event['quality_metrics']['success'] else "❌"
        total_ms = event['pipeline_metrics']['total_latency_ms']
        
        events_html += f"""
        <tr>
            <td>{timestamp}</td>
            <td>{status_icon}</td>
            <td>{event['character']}</td>
            <td>{event['source']}</td>
            <td>{total_ms:.0f}ms</td>
            <td>{event['context_metrics']['conversation_turn']}</td>
        </tr>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎤 Voice Agent Metrics</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; 
                padding: 20px; 
                background: #f8fafc;
                color: #1e293b;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ 
                background: white;
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 24px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .metrics-grid {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 20px; 
                margin-bottom: 24px;
            }}
            .metric-card {{ 
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .metric-value {{ 
                font-size: 24px; 
                font-weight: bold; 
                margin: 8px 0;
            }}
            .metric-label {{ 
                color: #64748b; 
                font-size: 14px;
                margin-bottom: 8px;
            }}
            .stage-grid {{ 
                display: grid; 
                grid-template-columns: repeat(3, 1fr); 
                gap: 16px; 
                margin: 16px 0;
            }}
            .stage-card {{ 
                background: #f8fafc;
                border-radius: 8px;
                padding: 16px;
                text-align: center;
                border: 2px solid #e2e8f0;
            }}
            .stage-value {{ 
                font-size: 20px; 
                font-weight: bold; 
                margin: 8px 0;
            }}
            .stage-label {{ 
                color: #64748b; 
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .recent-events {{ 
                background: white;
                border-radius: 12px;
                padding: 24px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            table {{ 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 16px;
            }}
            th, td {{ 
                padding: 12px; 
                text-align: left; 
                border-bottom: 1px solid #e2e8f0;
            }}
            th {{ 
                background: #f8fafc; 
                font-weight: 600;
                color: #475569;
                font-size: 14px;
            }}
            td {{ font-size: 14px; }}
            .refresh-btn {{
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                cursor: pointer;
                font-size: 14px;
                margin-left: 16px;
            }}
            .refresh-btn:hover {{ background: #2563eb; }}
            .status-good {{ color: #10B981; }}
            .status-warning {{ color: #F59E0B; }}
            .status-error {{ color: #EF4444; }}
        </style>
        <script>
            function refreshPage() {{
                window.location.reload();
            }}
            // Auto-refresh every 30 seconds
            setTimeout(refreshPage, 30000);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎤 Voice Agent Performance Dashboard</h1>
                <p>Real-time metrics for voice pipeline performance (Last 1 hour)</p>
                <button class="refresh-btn" onclick="refreshPage()">🔄 Refresh</button>
                <small style="color: #64748b; margin-left: 16px;">Auto-refreshes every 30 seconds</small>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Average Pipeline Latency</div>
                    <div class="metric-value">{avg_latency}</div>
                    <div style="font-size: 12px; color: #64748b;">Target: &lt;1500ms</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Success Rate</div>
                    <div class="metric-value">{success_rate}</div>
                    <div style="font-size: 12px; color: #64748b;">{summary['total_requests']} requests</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-label">Character Performance</div>
                    <div style="font-size: 14px; margin: 8px 0;">
                        <strong>Adina:</strong> {adina_display}<br>
                        <strong>Raffa:</strong> {raffa_display}
                    </div>
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Pipeline Stage Breakdown</div>
                <div class="stage-grid">
                    <div class="stage-card">
                        <div class="stage-label">STT</div>
                        <div class="stage-value" style="color: {stt_color};">{stt_avg}</div>
                    </div>
                    <div class="stage-card">
                        <div class="stage-label">LLM</div>
                        <div class="stage-value" style="color: {llm_color};">{llm_avg}</div>
                    </div>
                    <div class="stage-card">
                        <div class="stage-label">TTS</div>
                        <div class="stage-value" style="color: {tts_color};">{tts_avg}</div>
                    </div>
                </div>
            </div>
            
            <div class="recent-events">
                <h3>Recent Requests</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Status</th>
                            <th>Character</th>
                            <th>Source</th>
                            <th>Total Latency</th>
                            <th>Turn #</th>
                        </tr>
                    </thead>
                    <tbody>
                        {events_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

@router.get("/metrics/api/summary")
async def metrics_api_summary(hours: int = 1):
    """API endpoint for metrics summary"""
    metrics_service = get_metrics_service()
    return metrics_service.get_performance_summary(hours=hours)

@router.get("/metrics/api/events")
async def metrics_api_events(limit: int = 50):
    """API endpoint for recent events"""
    metrics_service = get_metrics_service()
    return metrics_service.get_recent_events(limit=limit) 