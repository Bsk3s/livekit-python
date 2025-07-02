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
from multiprocessing import Process

# Get current directory for subprocess calls
current_dir = Path(__file__).parent

def start_token_api():
    """Start the FastAPI token API server"""
    try:
        print("🌐 Starting Token API server...")
        from spiritual_voice_agent.main import app
        
        # Get port from environment (Render sets this)
        port = int(os.getenv('PORT', 8000))
        
        # Use Python module approach to run uvicorn
        import subprocess
        result = subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "spiritual_voice_agent.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--log-level", "info"
        ])
        
        if result.returncode != 0:
            print(f"❌ Token API exited with code {result.returncode}")
            
    except Exception as e:
        print(f"❌ Token API failed to start: {e}")
        sys.exit(1)

def start_agent_worker():
    """Start the LiveKit agent worker"""
    try:
        print("🤖 Starting LiveKit Agent Worker...")
        # Small delay to let the API start first
        time.sleep(2)
        
        # Import the CLI and run in development mode
        import subprocess
        import sys
        
        # Run the spiritual worker in development mode
        result = subprocess.run([
            sys.executable, 
            "spiritual_voice_agent/agents/spiritual_worker.py", 
            "dev"
        ], cwd=current_dir)
        
        if result.returncode != 0:
            print(f"❌ Agent worker exited with code {result.returncode}")
        
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
        # Monitor both processes - but prioritize keeping the Token API alive
        while True:
            if not api_process.is_alive():
                print("❌ Token API process died! This is critical - shutting down.")
                worker_process.terminate()
                sys.exit(1)
            
            if not worker_process.is_alive():
                print("⚠️ Agent Worker process died! Token API continues running.")
                print("📱 iOS app can still connect and get tokens.")
                print("🔄 Agent Worker will restart when users join rooms.")
                # Don't kill the API - just log and continue
                break  # Exit monitoring loop but keep API running
            
            time.sleep(5)  # Check every 5 seconds
        
        # If we get here, worker died but API is still running
        print("✅ Token API continues running independently")
        
        # Keep the main process alive to maintain the API
        while api_process.is_alive():
            time.sleep(10)
            
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main() 