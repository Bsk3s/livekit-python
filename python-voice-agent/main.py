#!/usr/bin/env python3
"""
Simple Railway entrypoint that starts the voice agent system
"""
import os
import subprocess
import sys

def main():
    """Main entrypoint for Railway deployment"""
    print("🚀 Starting Railway Voice Agent System")
    
    # Get Railway's dynamic port
    port = os.getenv("PORT", "10000")
    print(f"📡 Using port: {port}")
    
    # Set environment variables
    os.environ["PORT"] = str(port)
    
    # Import and run startup
    try:
        exec(open("startup.py").read())
    except Exception as e:
        print(f"❌ Error starting system: {e}")
        # Try alternative approach
        subprocess.run([sys.executable, "startup.py"])

if __name__ == "__main__":
    main()
