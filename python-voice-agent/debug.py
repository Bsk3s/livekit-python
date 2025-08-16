#!/usr/bin/env python3
"""
Render diagnostic script - shows exactly what files exist where
"""
import os
import sys
import subprocess

print("🔍 RENDER DIAGNOSTIC")
print("=" * 50)

print(f"PWD: {os.getcwd()}")
print(f"Python: {sys.executable}")
print(f"Python version: {sys.version}")

print("\n📁 Current directory contents:")
try:
    for item in sorted(os.listdir('.')):
        print(f"  {item}")
except Exception as e:
    print(f"  Error: {e}")

print("\n📁 /opt/render/project contents:")
try:
    for item in sorted(os.listdir('/opt/render/project')):
        print(f"  {item}")
except Exception as e:
    print(f"  Error: {e}")

print("\n📁 /opt/render/project/src contents:")
try:
    for item in sorted(os.listdir('/opt/render/project/src')):
        print(f"  {item}")
except Exception as e:
    print(f"  Error: {e}")

print("\n🔍 Finding main.py files:")
try:
    result = subprocess.run(['find', '/opt/render', '-name', 'main.py', '-type', 'f'], 
                          capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            print(f"  Found: {line}")
    else:
        print("  No main.py files found")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 50)
print("DIAGNOSTIC COMPLETE")
