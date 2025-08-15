#!/usr/bin/env python3
"""
Root level wrapper for Render deployment
Changes to src directory and runs the actual start script
"""
import os
import sys
import subprocess

def main():
    print("🚀 Root Level Wrapper - Starting Voice Agent Service...")
    print(f"📍 Current working directory: {os.getcwd()}")
    print(f"📁 Python executable: {sys.executable}")
    
    # Show what's in the current directory
    print("🔍 Contents of current directory:")
    try:
        for item in sorted(os.listdir('.')):
            item_path = os.path.join('.', item)
            if os.path.isdir(item_path):
                print(f"   📁 {item}/")
            else:
                print(f"   📄 {item}")
    except Exception as e:
        print(f"   ❌ Error listing directory: {e}")
    
    # Check if src directory exists and what's in it
    if os.path.exists('src'):
        print("🔍 Contents of src directory:")
        try:
            for item in sorted(os.listdir('src')):
                item_path = os.path.join('src', item)
                if os.path.isdir(item_path):
                    print(f"   📁 {item}/")
                else:
                    print(f"   📄 {item}")
        except Exception as e:
            print(f"   ❌ Error listing src directory: {e}")
        
        # Try to run the script from src directory
        src_script = os.path.join('src', 'start_unified_service.py')
        if os.path.exists(src_script):
            print(f"✅ Found script at: {src_script}")
            print("🔄 Changing to src directory and running script...")
            try:
                # Change to src directory and run the script
                os.chdir('src')
                print(f"📍 New working directory: {os.getcwd()}")
                
                # Run the actual start script
                result = subprocess.run([sys.executable, 'start_unified_service.py'], check=True)
                return True
            except Exception as e:
                print(f"❌ Error running script: {e}")
                return False
        else:
            print(f"❌ Script not found at: {src_script}")
    else:
        print("❌ src directory not found!")
    
    # Fallback: try to find and run startup.py directly
    print("🔍 Looking for startup.py as fallback...")
    for root, dirs, files in os.walk('.'):
        if 'startup.py' in files:
            startup_path = os.path.join(root, 'startup.py')
            print(f"✅ Found startup.py at: {startup_path}")
            try:
                result = subprocess.run([sys.executable, startup_path], check=True)
                return True
            except Exception as e:
                print(f"❌ Error running startup.py: {e}")
                continue
    
    print("💀 Could not find or run any startup script!")
    return False

if __name__ == "__main__":
    if not main():
        print("💀 Failed to start - exiting")
        sys.exit(1)