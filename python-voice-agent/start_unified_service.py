#!/usr/bin/env python3
"""
Unified Spiritual Guidance Service
Runs both the FastAPI token API and LiveKit agent worker together
"""

import asyncio
import os
import signal
import subprocess
import sys
import threading
import time
from multiprocessing import Process
from pathlib import Path

import requests

# Get current directory for subprocess calls
current_dir = Path(__file__).parent


def start_token_api():
    """Start the FastAPI token API server"""
    try:
        print("🌐 Starting Token API server...")
        from spiritual_voice_agent.main import app

        # Get port from environment (Railway sets this)
        port = int(os.getenv("PORT", 10000))

        # Use Python module approach to run uvicorn
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "spiritual_voice_agent.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--log-level",
                "info",
            ]
        )

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

        # Run the spiritual worker in development mode as a module
        result = subprocess.run(
            [sys.executable, "-m", "spiritual_voice_agent.agents.spiritual_worker", "dev"],
            cwd=current_dir,
        )

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

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kokoro_dir = os.path.join(script_dir, "spiritual_voice_agent", "services", "tts", "implementations", "kokoro")
    
    # Create kokoro directory if it doesn't exist
    os.makedirs(kokoro_dir, exist_ok=True)
    
    print("Downloading kokoro model...")
    kokoro_model_path = os.path.join(kokoro_dir, "kokoro-v1.0.onnx")
    if not os.path.exists(kokoro_model_path):
        model = requests.get(
            "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
        )
        with open(kokoro_model_path, "wb") as f:
            f.write(model.content)
    
    voices_model_path = os.path.join(kokoro_dir, "voices-v1.0.bin")
    if not os.path.exists(voices_model_path):
        voices = requests.get(
            "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
        )
        with open(voices_model_path, "wb") as f:
            f.write(voices.content)

    # Download LiveKit turn detector models if on Railway
    if os.getenv("RAILWAY_ENVIRONMENT"):
        print("🤖 Downloading LiveKit turn detector models...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "spiritual_voice_agent.agents.spiritual_worker", "download-files"],
                cwd=current_dir,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            if result.returncode == 0:
                print("✅ LiveKit models downloaded successfully")
            else:
                print(f"⚠️ LiveKit model download completed with warnings: {result.stderr}")
        except Exception as e:
            print(f"⚠️ LiveKit model download failed (will retry at runtime): {e}")

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
