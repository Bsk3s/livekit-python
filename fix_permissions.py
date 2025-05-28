#!/usr/bin/env python3
"""
Fix permissions for spiritual_worker.py to make it executable on Render
"""

import os
import stat
from pathlib import Path

def fix_worker_permissions():
    """Make the spiritual worker executable"""
    worker_path = Path("python-voice-agent/app/agents/spiritual_worker.py")
    
    if worker_path.exists():
        # Add execute permission
        current_mode = worker_path.stat().st_mode
        worker_path.chmod(current_mode | stat.S_IEXEC)
        print(f"✅ Made {worker_path} executable")
        
        # Verify
        if worker_path.stat().st_mode & stat.S_IEXEC:
            print(f"🔓 File is now executable")
        else:
            print(f"❌ Failed to make file executable")
    else:
        print(f"❌ File not found: {worker_path}")

if __name__ == "__main__":
    fix_worker_permissions() 