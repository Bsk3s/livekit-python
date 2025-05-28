#!/usr/bin/env python3
"""
Test environment setup for Spiritual Agent Worker
"""

import os
import sys
from pathlib import Path

def check_environment():
    """Check if all required environment variables are set"""
    print("🔍 Checking Environment Variables for Worker")
    print("=" * 50)
    
    required_vars = [
        'LIVEKIT_URL',
        'LIVEKIT_API_KEY', 
        'LIVEKIT_API_SECRET',
        'DEEPGRAM_API_KEY',
        'OPENAI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * (len(value) - 4)}{value[-4:]}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    return missing_vars

def check_dependencies():
    """Check if required packages are available"""
    print("\n🔍 Checking Dependencies")
    print("=" * 30)
    
    required_packages = [
        'livekit',
        'livekit.agents',
        'livekit.plugins.deepgram',
        'livekit.plugins.openai', 
        'livekit.plugins.silero',
        'openai',
        'deepgram'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError as e:
            print(f"❌ {package}: {e}")
            missing_packages.append(package)
    
    return missing_packages

def check_worker_file():
    """Check if worker file exists and is valid"""
    print("\n🔍 Checking Worker File")
    print("=" * 25)
    
    worker_path = Path("python-voice-agent/app/agents/spiritual_worker.py")
    
    if worker_path.exists():
        print(f"✅ Worker file exists: {worker_path}")
        
        # Check if it's executable
        try:
            with open(worker_path, 'r') as f:
                content = f.read()
                if 'def main():' in content and 'cli.run_app' in content:
                    print("✅ Worker file structure looks correct")
                    return True
                else:
                    print("❌ Worker file missing main() or cli.run_app")
                    return False
        except Exception as e:
            print(f"❌ Error reading worker file: {e}")
            return False
    else:
        print(f"❌ Worker file not found: {worker_path}")
        return False

def main():
    """Main test function"""
    print("🌟 Testing Worker Environment Setup")
    print("🕐 Started at:", os.popen('date').read().strip())
    print("=" * 60)
    
    # Check environment variables
    missing_vars = check_environment()
    
    # Check dependencies  
    missing_packages = check_dependencies()
    
    # Check worker file
    worker_valid = check_worker_file()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 WORKER READINESS SUMMARY")
    print("=" * 60)
    
    if not missing_vars and not missing_packages and worker_valid:
        print("✅ Worker is ready for deployment!")
        print("\n🚀 Next steps:")
        print("1. Commit and push changes to trigger Render re-deployment")
        print("2. Check Render dashboard for both services")
        print("3. Monitor worker logs for successful startup")
        return 0
    else:
        print("❌ Worker has issues that need to be resolved:")
        
        if missing_vars:
            print(f"\n🔧 Missing environment variables: {missing_vars}")
            print("   → Set these in your Render dashboard")
        
        if missing_packages:
            print(f"\n📦 Missing packages: {missing_packages}")
            print("   → Check requirements.txt includes all dependencies")
        
        if not worker_valid:
            print("\n📄 Worker file issues")
            print("   → Check spiritual_worker.py exists and is correct")
        
        return 1

if __name__ == "__main__":
    sys.exit(main()) 