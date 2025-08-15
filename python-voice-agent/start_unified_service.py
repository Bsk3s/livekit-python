#!/usr/bin/env python3
"""
Unified service starter for cloud deployment (Render/Railway)
"""
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run our startup system
if __name__ == "__main__":
    print("🚀 Starting Unified Voice Agent Service...")
    
    # Use our existing startup.py
    exec(open("startup.py").read())
