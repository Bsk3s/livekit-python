#!/usr/bin/env python3
"""
Sanity check script - validates all dependencies work
"""
import sys
import subprocess

def main():
    print("🔍 SANITY CHECK - Voice Agent Dependencies")
    print("=" * 50)
    
    print(f"🐍 Python: {sys.version}")
    
    print("\n📦 Testing imports:")
    
    # Test livekit core
    try:
        import livekit
        print(f"  ✅ livekit")
    except ImportError as e:
        print(f"  ❌ livekit: {e}")
        return False
    
    # Test livekit agents
    try:
        from livekit import agents
        print(f"  ✅ livekit.agents")
    except ImportError as e:
        print(f"  ❌ livekit.agents: {e}")
        return False
    
    # Test other critical modules
    modules = [
        ("av", "av"),
        ("httpx", "httpx"),
        ("python-dotenv", "dotenv"),
        ("openai", "openai"),
        ("deepgram", "deepgram"),
        ("numpy", "numpy")
    ]
    
    for display_name, module_name in modules:
        try:
            __import__(module_name)
            print(f"  ✅ {display_name}")
        except ImportError as e:
            print(f"  ❌ {display_name}: {e}")
            return False
    
    # Test ffmpeg
    print("\n🎵 Testing ffmpeg:")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=10
        )
        print("  ✅ ffmpeg available")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("  ❌ ffmpeg not available or failed")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 SANITY CHECK PASSED - All dependencies working!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)