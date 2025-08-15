#!/usr/bin/env python3
"""
Unified service starter for cloud deployment (Render/Railway)
"""
import os
import sys
import subprocess

def find_and_run_startup():
    """Find startup.py and run it from the correct location"""
    
    # Possible locations for startup.py
    possible_paths = [
        "startup.py",                    # Current directory
        "./startup.py",                  # Explicit current
        "../startup.py",                 # Parent directory
        "/app/startup.py",              # Docker path (Railway)
        "/opt/render/project/startup.py",  # Render root path
        "/opt/render/project/src/startup.py",  # Render src path
        os.path.join(os.path.dirname(__file__), "startup.py"),  # Same dir as this file
    ]
    
    print("🔍 Searching for startup.py...")
    print(f"Current working directory: {os.getcwd()}")
    print(f"This file location: {__file__}")
    print(f"Environment variables:")
    for key in ['PATH', 'RENDER', 'PORT', 'PROJECT_ROOT']:
        if key in os.environ:
            print(f"  {key}={os.environ[key]}")
    
    # List all files in current directory
    print("Files in current directory:")
    try:
        for f in sorted(os.listdir(".")):
            full_path = os.path.join(".", f)
            if os.path.isdir(full_path):
                print(f"  📁 {f}/")
            else:
                print(f"  📄 {f}")
    except Exception as e:
        print(f"  Error listing files: {e}")
    
    # Also check parent directory
    print("Files in parent directory:")
    try:
        parent_dir = os.path.dirname(os.getcwd())
        for f in sorted(os.listdir(parent_dir)):
            full_path = os.path.join(parent_dir, f)
            if os.path.isdir(full_path):
                print(f"  📁 {f}/")
            else:
                print(f"  📄 {f}")
    except Exception as e:
        print(f"  Error listing parent files: {e}")
    
    # Try each possible path
    for path in possible_paths:
        print(f"Trying: {path}")
        if os.path.exists(path):
            print(f"✅ Found startup.py at: {path}")
            try:
                # Run it directly with Python
                result = subprocess.run([sys.executable, path], check=True)
                return True
            except Exception as e:
                print(f"❌ Error running {path}: {e}")
                continue
        else:
            print(f"❌ Not found: {path}")
    
    print("❌ Could not find startup.py anywhere!")
    return False

if __name__ == "__main__":
    print("🚀 Starting Unified Voice Agent Service...")
    
    if not find_and_run_startup():
        print("💀 Failed to start - exiting")
        sys.exit(1)
