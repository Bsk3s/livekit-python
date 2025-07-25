#!/usr/bin/env python3
"""
Start Simple Working Voice Agent (1.0 Patterns)
"""

import subprocess
import sys
import os

def main():
    print("🚀 Starting Simple Working Voice Agent (1.0 Patterns)...")
    print("📂 Working directory:", os.getcwd())
    
    # Make sure we're in the virtual environment
    if not os.environ.get('VIRTUAL_ENV'):
        print("⚠️  Virtual environment not detected. Run:")
        print("   source venv/bin/activate")
        sys.exit(1)
    
    try:
        # Run the simple agent
        cmd = ["python", "-m", "simple_working_agent.main", "dev"]
        print(f"🔧 Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running simple agent: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Simple agent stopped by user")

if __name__ == "__main__":
    main() 