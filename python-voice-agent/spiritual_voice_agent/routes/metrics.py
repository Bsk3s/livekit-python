from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from spiritual_voice_agent.services.metrics_service import get_metrics_service

router = APIRouter()

@router.get("/metrics", response_class=HTMLResponse)
async def metrics_dashboard():
    """Zero-latency metrics dashboard"""
    metrics_service = get_metrics_service()
    summary = metrics_service.get_performance_summary(hours=1)
    recent_events = await metrics_service.get_recent_events(limit=10)
    
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
    
    # System stats from zero-latency metrics
    system_stats = summary.get('system_stats', {})
    events_queued = system_stats.get('events_queued', 0)
    events_processed = system_stats.get('events_processed', 0)
    events_dropped = system_stats.get('events_dropped', 0)
    queue_full_count = system_stats.get('queue_full_count', 0)
    
    # Processing rate
    processing_rate = f"{(events_processed / max(events_queued, 1) * 100):.1f}%" if events_queued > 0 else "N/A"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎤 Voice Agent Performance Dashboard</title>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="30">
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                min-height: 100vh;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 40px;
                padding-bottom: 20px;
                border-bottom: 2px solid #e1e5e9;
            }}
            .header h1 {{
                margin: 0;
                font-size: 2.5em;
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 700;
            }}
            .subtitle {{
                color: #666;
                margin-top: 10px;
                font-size: 1.1em;
            }}
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 25px;
                margin-bottom: 30px;
            }}
            .metric-card {{
                background: white;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                border-left: 4px solid #667eea;
                transition: transform 0.2s ease;
            }}
            .metric-card:hover {{
                transform: translateY(-2px);
            }}
            .metric-title {{
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #8e9aaf;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            .metric-value {{
                font-size: 2.2em;
                font-weight: 700;
                color: #2d3748;
                margin-bottom: 5px;
            }}
            .metric-subtitle {{
                color: #718096;
                font-size: 0.9em;
            }}
            .pipeline-breakdown {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 20px;
                margin: 30px 0;
            }}
            .stage-card {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                box-shadow: 0 3px 15px rgba(0,0,0,0.06);
            }}
            .stage-card.stt {{ border-top: 3px solid #48bb78; }}
            .stage-card.llm {{ border-top: 3px solid #ed8936; }}
            .stage-card.tts {{ border-top: 3px solid #9f7aea; }}
            .stage-name {{
                font-weight: 600;
                margin-bottom: 8px;
                text-transform: uppercase;
                font-size: 0.85em;
                letter-spacing: 0.5px;
            }}
            .stage-value {{
                font-size: 1.8em;
                font-weight: 700;
            }}
            .stt .stage-name {{ color: #48bb78; }}
            .llm .stage-name {{ color: #ed8936; }}
            .tts .stage-name {{ color: #9f7aea; }}
            .stt .stage-value {{ color: #38a169; }}
            .llm .stage-value {{ color: #dd6b20; }}
            .tts .stage-value {{ color: #805ad5; }}
            .character-section {{
                margin-top: 30px;
                background: white;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }}
            .section-title {{
                font-size: 1.3em;
                font-weight: 600;
                margin-bottom: 20px;
                color: #2d3748;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 10px;
            }}
            .character-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
            }}
            .character-card {{
                background: #f7fafc;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
            }}
            .character-name {{
                font-weight: 600;
                margin-bottom: 10px;
                text-transform: capitalize;
                color: #4a5568;
            }}
            .character-stats {{
                color: #718096;
                font-size: 0.9em;
            }}
            .system-stats {{
                margin-top: 30px;
                background: white;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}
            .stat-item {{
                text-align: center;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 8px;
            }}
            .stat-value {{
                font-size: 1.5em;
                font-weight: 600;
                color: #2d3748;
            }}
            .stat-label {{
                font-size: 0.8em;
                color: #718096;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-top: 5px;
            }}
            .refresh-notice {{
                text-align: center;
                color: #718096;
                font-size: 0.9em;
                margin-top: 20px;
                padding: 15px;
                background: #f1f5f9;
                border-radius: 8px;
            }}
            .no-data {{
                color: #a0aec0;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎤 Voice Agent Performance Dashboard</h1>
                <div class="subtitle">Real-time metrics for voice pipeline performance (Last 1 hour)</div>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Average Pipeline Latency</div>
                    <div class="metric-value">{avg_latency}</div>
                    <div class="metric-subtitle">Target: &lt;500ms</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">Success Rate</div>
                    <div class="metric-value">{success_rate}</div>
                    <div class="metric-subtitle">{summary['total_requests']} requests</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">🚀 Cost Analytics</div>
                    <div class="metric-value">Calculating...</div>
                    <div class="metric-subtitle">Cost tracking system starting up</div>
                </div>
            </div>
            
            <div class="section-title">Pipeline Stage Breakdown</div>
            <div class="pipeline-breakdown">
                <div class="stage-card stt">
                    <div class="stage-name">STT</div>
                    <div class="stage-value">{stt_avg}</div>
                </div>
                
                <div class="stage-card llm">
                    <div class="stage-name">LLM</div>
                    <div class="stage-value">{llm_avg}</div>
                </div>
                
                <div class="stage-card tts">
                    <div class="stage-name">TTS</div>
                    <div class="stage-value">{tts_avg}</div>
                </div>
            </div>
            
            <div class="character-section">
                <div class="section-title">Character Performance</div>
                <div class="character-grid">
                    <div class="character-card">
                        <div class="character-name">Adina</div>
                        <div class="character-stats">{adina_display}</div>
                    </div>
                    
                    <div class="character-card">
                        <div class="character-name">Raffa</div>
                        <div class="character-stats">{raffa_display}</div>
                    </div>
                </div>
            </div>
            
            <div class="system-stats">
                <div class="section-title">🚀 Zero-Latency Metrics System</div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{events_queued}</div>
                        <div class="stat-label">Events Queued</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{events_processed}</div>
                        <div class="stat-label">Events Processed</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{processing_rate}</div>
                        <div class="stat-label">Processing Rate</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{events_dropped}</div>
                        <div class="stat-label">Events Dropped</div>
                    </div>
                </div>
            </div>
            
            <div class="refresh-notice">
                📊 Dashboard auto-refreshes every 30 seconds | Zero voice latency impact ✨
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

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