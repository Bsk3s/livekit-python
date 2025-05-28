#!/usr/bin/env python3
"""
Simple startup script for the Spiritual Guidance LiveKit Agent Worker.
This script avoids path issues by being in the root directory.
"""

import sys
import os
from pathlib import Path

# Add the python-voice-agent directory to the Python path
current_dir = Path(__file__).parent
agent_dir = current_dir / "python-voice-agent"
sys.path.insert(0, str(agent_dir))

# Change to the agent directory for proper relative imports
os.chdir(str(agent_dir))

if __name__ == "__main__":
    # Import and run the worker
    try:
        print("🌟 Starting Spiritual Guidance Agent Worker...")
        print(f"📂 Working directory: {os.getcwd()}")
        print(f"🐍 Python path: {sys.path[:3]}...")
        
        # Import the main function from the worker
        from app.agents.spiritual_worker import main
        
        # Start the worker
        main()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start worker: {e}")
        sys.exit(1) 