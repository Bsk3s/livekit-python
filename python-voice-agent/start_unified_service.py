#!/usr/bin/env python3
"""
Unified Spiritual Guidance Service
Runs both the FastAPI token API and LiveKit agent worker together
"""

import asyncio
import os
import sys
import signal
import threading
import time
from pathlib import Path
import uvicorn
from multiprocessing import Process

# Add the current directory to the Python path since we're already in python-voice-agent
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def start_token_api():
    """Start the FastAPI token API server"""
    try:
        print("🌐 Starting Token API server...")
        from app.main import app
        
        # Get port from environment (Render sets this)
        port = int(os.getenv('PORT', 8000))
        
        # Start uvicorn server
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        print(f"❌ Token API failed to start: {e}")
        sys.exit(1)

def start_agent_worker():
    """Start the LiveKit agent worker"""
    try:
        print("🤖 Starting LiveKit Agent Worker...")
        # Small delay to let the API start first
        time.sleep(2)
        
        from app.agents.spiritual_worker import main
        main()
    except Exception as e:
        print(f"❌ Agent Worker failed to start: {e}")
        sys.exit(1)

def main():
    """Main function that starts both services"""
    print("🌟 Starting Unified Spiritual Guidance Service...")
    print(f"📂 Working directory: {os.getcwd()}")
    print("🚀 Launching both Token API and Agent Worker...")
    
    # Start token API in a separate process
    api_process = Process(target=start_token_api)
    api_process.start()
    
    # Start agent worker in a separate process  
    worker_process = Process(target=start_agent_worker)
    worker_process.start()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n📡 Received signal {signum}, shutting down both services...")
        api_process.terminate()
        worker_process.terminate()
        api_process.join(timeout=5)
        worker_process.join(timeout=5)
        print("👋 Unified service shutdown complete")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Monitor both processes
        while True:
            if not api_process.is_alive():
                print("❌ Token API process died!")
                worker_process.terminate()
                sys.exit(1)
            
            if not worker_process.is_alive():
                print("❌ Agent Worker process died!")
                api_process.terminate()
                sys.exit(1)
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main() 