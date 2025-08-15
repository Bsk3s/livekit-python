#!/usr/bin/env python3
"""
Railway Complete Startup - API Server + Voice Agent
"""
import os
import subprocess
import sys
import time

def start_api_server():
    """Start the FastAPI server"""
    port = os.getenv("PORT", "10000")
    print(f"🌐 Starting API server on port {port}")
    
    api_cmd = [
        sys.executable, "-m", "uvicorn",
        "spiritual_voice_agent.main_minimal:app",
        "--host", "0.0.0.0",
        "--port", port,
        "--workers", "1"
    ]
    
    return subprocess.Popen(api_cmd)

def start_voice_agent():
    """Start the LiveKit voice agent worker"""
    print("🎙️ Starting voice agent worker")
    
    # Set environment variables for the agent
    env = os.environ.copy()
    env['LIVEKIT_URL'] = os.getenv('LIVEKIT_URL', '')
    env['LIVEKIT_API_KEY'] = os.getenv('LIVEKIT_API_KEY', '')
    env['LIVEKIT_API_SECRET'] = os.getenv('LIVEKIT_API_SECRET', '')
    env['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')
    env['DEEPGRAM_API_KEY'] = os.getenv('DEEPGRAM_API_KEY', '')
    
    agent_cmd = [
        sys.executable, "railway_agent.py", "dev"
    ]
    
    print(f"🔧 Agent environment: LIVEKIT_URL={env.get('LIVEKIT_URL', 'NOT_SET')}")
    
    return subprocess.Popen(agent_cmd, env=env)

if __name__ == "__main__":
    print("🚀 Railway Complete Voice AI Startup")
    
    # Check environment variables
    required_vars = ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET', 'OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
    else:
        print("✅ All required environment variables present")
    
    # Start API server
    api_process = start_api_server()
    
    # Wait for API to be ready
    print("⏱️ Waiting for API server to start...")
    time.sleep(8)
    
    # Start voice agent worker
    try:
        agent_process = start_voice_agent()
        print("✅ Both API server and voice agent started")
        print("🎯 Ready for voice conversations!")
    except Exception as e:
        print(f"❌ Failed to start voice agent: {e}")
        agent_process = None
    
    try:
        # Monitor both processes
        print("🔍 Monitoring processes...")
        while True:
            if api_process.poll() is not None:
                print("❌ API process died")
                break
            if agent_process and agent_process.poll() is not None:
                print("❌ Agent process died")
                break
            time.sleep(10)
    except KeyboardInterrupt:
        print("🛑 Shutting down...")
        api_process.terminate()
        if agent_process:
            agent_process.terminate()