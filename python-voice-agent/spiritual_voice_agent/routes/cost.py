"""
Internal Cost Analytics Dashboard

Business intelligence dashboard for voice agent cost tracking and financial analysis.
For internal use only - provides detailed cost breakdown, user economics, and business metrics.

Route: /cost
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from spiritual_voice_agent.services.cost_analytics import get_cost_analytics_db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/cost", response_class=HTMLResponse)
async def cost_dashboard():
    """Internal cost analytics dashboard"""
    
    try:
        cost_db = get_cost_analytics_db()
        
        # Get cost data for different time periods
        daily_summary = cost_db.get_cost_summary(days=1)
        weekly_summary = cost_db.get_cost_summary(days=7)
        monthly_summary = cost_db.get_cost_summary(days=30)
        
        # Recent cost events for detailed view
        recent_events = []
        try:
            # Get recent events from database
            import sqlite3
            with sqlite3.connect(cost_db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT session_id, user_id, character, timestamp, 
                           stt_cost, llm_cost, tts_cost, total_cost,
                           transcript_text, response_text, success
                    FROM cost_events 
                    WHERE cost_calculated = TRUE
                    ORDER BY timestamp DESC 
                    LIMIT 20
                """)
                recent_events = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Could not fetch recent cost events: {e}")
        
        # Format cost displays
        def format_cost_summary(summary, period_name):
            if summary['total_conversations'] == 0:
                return {
                    'total_cost': '$0.0000',
                    'avg_cost': '$0.0000',
                    'conversations': 0,
                    'users': 0,
                    'stt_cost': '$0.0000',
                    'llm_cost': '$0.0000', 
                    'tts_cost': '$0.0000',
                    'period': period_name
                }
            
            return {
                'total_cost': f"${summary['total_cost']:.4f}",
                'avg_cost': f"${summary['avg_cost_per_turn']:.4f}",
                'conversations': summary['total_conversations'],
                'users': summary['unique_users'],
                'stt_cost': f"${summary['total_stt_cost']:.4f}",
                'llm_cost': f"${summary['total_llm_cost']:.4f}",
                'tts_cost': f"${summary['total_tts_cost']:.4f}",
                'period': period_name
            }
        
        daily = format_cost_summary(daily_summary, "24 Hours")
        weekly = format_cost_summary(weekly_summary, "7 Days") 
        monthly = format_cost_summary(monthly_summary, "30 Days")
        
        # Recent events table
        events_html = ""
        for event in recent_events[:10]:  # Show last 10
            timestamp = str(event.get('timestamp', ''))[:19] if event.get('timestamp') else 'N/A'
            user_id = event.get('user_id', 'N/A')[:12]  # Truncate for display
            character = event.get('character', 'N/A')
            total_cost = event.get('total_cost', 0) or 0
            success_icon = "✅" if event.get('success') else "❌"
            
            # Truncate text for display
            transcript = (event.get('transcript_text') or '')[:50] + '...' if len(event.get('transcript_text') or '') > 50 else (event.get('transcript_text') or 'N/A')
            
            events_html += f"""
            <tr>
                <td>{timestamp}</td>
                <td>{success_icon}</td>
                <td>{user_id}</td>
                <td>{character}</td>
                <td>${total_cost:.6f}</td>
                <td>{transcript}</td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>💰 Internal Cost Analytics</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0; 
                    padding: 20px; 
                    background: #f1f5f9;
                    color: #1e293b;
                }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                .header {{ 
                    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
                    color: white;
                    border-radius: 12px;
                    padding: 24px;
                    margin-bottom: 24px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .period-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); 
                    gap: 24px; 
                    margin-bottom: 32px;
                }}
                .period-card {{ 
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    border-left: 4px solid #3b82f6;
                }}
                .period-title {{ 
                    font-size: 18px; 
                    font-weight: 600; 
                    color: #1e293b;
                    margin-bottom: 16px;
                }}
                .cost-main {{ 
                    font-size: 32px; 
                    font-weight: bold; 
                    color: #1e40af;
                    margin: 8px 0;
                }}
                .cost-sub {{ 
                    font-size: 14px; 
                    color: #64748b;
                    margin: 4px 0;
                }}
                .breakdown-grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(3, 1fr); 
                    gap: 12px; 
                    margin: 16px 0;
                }}
                .breakdown-item {{ 
                    background: #f8fafc;
                    border-radius: 8px;
                    padding: 12px;
                    text-align: center;
                }}
                .breakdown-value {{ 
                    font-size: 16px; 
                    font-weight: bold; 
                    color: #374151;
                }}
                .breakdown-label {{ 
                    font-size: 12px; 
                    color: #6b7280;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 16px;
                    margin: 16px 0;
                }}
                .stat-item {{
                    background: #fef3c7;
                    border-radius: 8px;
                    padding: 12px;
                    text-align: center;
                }}
                .stat-value {{
                    font-size: 20px;
                    font-weight: bold;
                    color: #92400e;
                }}
                .stat-label {{
                    font-size: 12px;
                    color: #a16207;
                }}
                .recent-events {{ 
                    background: white;
                    border-radius: 12px;
                    padding: 24px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .section-title {{
                    font-size: 20px;
                    font-weight: 600;
                    color: #1e293b;
                    margin-bottom: 16px;
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
                    font-size: 14px;
                }}
                th {{ 
                    background: #f8fafc; 
                    font-weight: 600;
                    color: #475569;
                }}
                .refresh-btn {{
                    background: white;
                    color: #1e40af;
                    border: 2px solid #3b82f6;
                    border-radius: 8px;
                    padding: 8px 16px;
                    cursor: pointer;
                    font-size: 14px;
                    margin-left: 16px;
                }}
                .refresh-btn:hover {{ 
                    background: #eff6ff; 
                }}
                .internal-badge {{
                    background: #fecaca;
                    color: #991b1b;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 600;
                    margin-left: 12px;
                }}
            </style>
            <script>
                function refreshPage() {{
                    window.location.reload();
                }}
                // Auto-refresh every 60 seconds (slower than public metrics)
                setTimeout(refreshPage, 60000);
            </script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>💰 Internal Cost Analytics Dashboard</h1>
                    <p>Business intelligence for voice agent financial tracking</p>
                    <span class="internal-badge">INTERNAL USE ONLY</span>
                    <button class="refresh-btn" onclick="refreshPage()">🔄 Refresh</button>
                    <small style="opacity: 0.8; margin-left: 16px;">Auto-refreshes every 60 seconds</small>
                </div>
                
                <div class="period-grid">
                    <div class="period-card">
                        <div class="period-title">📅 {daily['period']}</div>
                        <div class="cost-main">{daily['total_cost']}</div>
                        <div class="cost-sub">Average: {daily['avg_cost']} per turn</div>
                        
                        <div class="breakdown-grid">
                            <div class="breakdown-item">
                                <div class="breakdown-value">{daily['stt_cost']}</div>
                                <div class="breakdown-label">STT</div>
                            </div>
                            <div class="breakdown-item">
                                <div class="breakdown-value">{daily['llm_cost']}</div>
                                <div class="breakdown-label">LLM</div>
                            </div>
                            <div class="breakdown-item">
                                <div class="breakdown-value">{daily['tts_cost']}</div>
                                <div class="breakdown-label">TTS</div>
                            </div>
                        </div>
                        
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-value">{daily['conversations']}</div>
                                <div class="stat-label">Conversations</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">{daily['users']}</div>
                                <div class="stat-label">Users</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="period-card">
                        <div class="period-title">📊 {weekly['period']}</div>
                        <div class="cost-main">{weekly['total_cost']}</div>
                        <div class="cost-sub">Average: {weekly['avg_cost']} per turn</div>
                        
                        <div class="breakdown-grid">
                            <div class="breakdown-item">
                                <div class="breakdown-value">{weekly['stt_cost']}</div>
                                <div class="breakdown-label">STT</div>
                            </div>
                            <div class="breakdown-item">
                                <div class="breakdown-value">{weekly['llm_cost']}</div>
                                <div class="breakdown-label">LLM</div>
                            </div>
                            <div class="breakdown-item">
                                <div class="breakdown-value">{weekly['tts_cost']}</div>
                                <div class="breakdown-label">TTS</div>
                            </div>
                        </div>
                        
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-value">{weekly['conversations']}</div>
                                <div class="stat-label">Conversations</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">{weekly['users']}</div>
                                <div class="stat-label">Users</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="period-card">
                        <div class="period-title">📈 {monthly['period']}</div>
                        <div class="cost-main">{monthly['total_cost']}</div>
                        <div class="cost-sub">Average: {monthly['avg_cost']} per turn</div>
                        
                        <div class="breakdown-grid">
                            <div class="breakdown-item">
                                <div class="breakdown-value">{monthly['stt_cost']}</div>
                                <div class="breakdown-label">STT</div>
                            </div>
                            <div class="breakdown-item">
                                <div class="breakdown-value">{monthly['llm_cost']}</div>
                                <div class="breakdown-label">LLM</div>
                            </div>
                            <div class="breakdown-item">
                                <div class="breakdown-value">{monthly['tts_cost']}</div>
                                <div class="breakdown-label">TTS</div>
                            </div>
                        </div>
                        
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-value">{monthly['conversations']}</div>
                                <div class="stat-label">Conversations</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">{monthly['users']}</div>
                                <div class="stat-label">Users</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="recent-events">
                    <div class="section-title">💬 Recent Cost Events</div>
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Status</th>
                                <th>User ID</th>
                                <th>Character</th>
                                <th>Total Cost</th>
                                <th>Transcript Preview</th>
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
        
    except Exception as e:
        logger.error(f"Error in cost dashboard: {e}")
        # Return error page
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>💰 Cost Analytics - Error</title>
        </head>
        <body style="font-family: system-ui; padding: 40px; text-align: center;">
            <h1>💰 Cost Analytics</h1>
            <p>Cost tracking system starting up...</p>
            <p style="color: #666;">Error: {e}</p>
            <button onclick="window.location.reload()" style="padding: 12px 24px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer;">🔄 Retry</button>
        </body>
        </html>
        """


@router.get("/cost/api/summary")
async def cost_api_summary(days: int = 7):
    """API endpoint for cost summary data"""
    try:
        cost_db = get_cost_analytics_db()
        return cost_db.get_cost_summary(days=days)
    except Exception as e:
        logger.error(f"Cost API error: {e}")
        return {"error": str(e), "available": False}


@router.get("/cost/api/user/{user_id}")
async def cost_api_user(user_id: str, days: int = 30):
    """API endpoint for user-specific cost data"""
    try:
        cost_db = get_cost_analytics_db()
        events = cost_db.get_user_costs(user_id, days=days)
        total_cost = sum(event.get('total_cost', 0) or 0 for event in events if event.get('cost_calculated'))
        
        return {
            "user_id": user_id,
            "total_cost": total_cost,
            "conversation_count": len(events),
            "events": events
        }
    except Exception as e:
        logger.error(f"User cost API error: {e}")
        return {"error": str(e), "user_id": user_id} 