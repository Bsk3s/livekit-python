#!/usr/bin/env python3
"""
Railway app.py - Standard Flask/Railway naming convention
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run our main startup
if __name__ == "__main__":
    print("🚀 Railway Voice Agent - Starting via app.py")
    
    # Execute main.py
    exec(open("main.py").read())
