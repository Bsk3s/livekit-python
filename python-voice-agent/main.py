#!/usr/bin/env python3
"""
🚀 SPIRITUAL VOICE AGENT - PRODUCTION ENTRY POINT
Single file that starts the complete voice agent system
Works on Railway, Render, Docker, and locally
"""
import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Load environment variables
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class VoiceAgentSystem:
    """Complete Voice Agent System Manager"""
    
    def __init__(self):
        self.api_process = None
        self.agent_process = None
        self.port = os.getenv("PORT", "10000")
        
    def check_environment(self):
        """Check and validate environment variables"""
        logger.info("🔍 Checking environment configuration...")
        
        required_vars = [
            'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET', 
            'OPENAI_API_KEY', 'DEEPGRAM_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.warning(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
            logger.warning("⚠️ Some features may not work properly")
        else:
            logger.info("✅ All required environment variables present")
            
        # Log configuration summary (without exposing secrets)
        logger.info(f"🌐 Port: {self.port}")
        logger.info(f"🔗 LiveKit URL: {os.getenv('LIVEKIT_URL', 'NOT_SET')}")
        logger.info(f"🔑 API Keys configured: {len([v for v in required_vars if os.getenv(v)]) }/{len(required_vars)}")
        
    def start_api_server(self):
        """Start the FastAPI server"""
        logger.info(f"🌐 Starting API server on port {self.port}")
        
        # Use the main FastAPI app from spiritual_voice_agent
        api_cmd = [
            sys.executable, "-m", "uvicorn",
            "spiritual_voice_agent.main:app",
            "--host", "0.0.0.0", 
            "--port", str(self.port),
            "--workers", "1"
        ]
        
        try:
            self.api_process = subprocess.Popen(
                api_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            logger.info("✅ API server process started")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start API server: {e}")
            return False
    
    def start_voice_agent(self):
        """Start the LiveKit voice agent worker"""
        logger.info("🎙️ Starting voice agent worker")
        
        # Prepare environment for agent
        env = os.environ.copy()
        
        # Use the railway agent (which is production-ready)
        agent_cmd = [sys.executable, "railway_agent.py", "dev"]
        
        try:
            self.agent_process = subprocess.Popen(
                agent_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, 
                universal_newlines=True
            )
            logger.info("✅ Voice agent worker started")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start voice agent: {e}")
            return False
    
    def monitor_processes(self):
        """Monitor both processes and restart if needed"""
        logger.info("🔍 Monitoring system processes...")
        
        try:
            while True:
                # Check API process
                if self.api_process and self.api_process.poll() is not None:
                    logger.error("❌ API server process died")
                    break
                    
                # Check agent process  
                if self.agent_process and self.agent_process.poll() is not None:
                    logger.error("❌ Voice agent process died")
                    break
                    
                # Log status every 60 seconds
                time.sleep(60)
                logger.info("💚 System running normally")
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested")
        except Exception as e:
            logger.error(f"❌ Monitor error: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown all processes"""
        logger.info("🛑 Shutting down voice agent system...")
        
        if self.api_process:
            try:
                self.api_process.terminate()
                self.api_process.wait(timeout=10)
                logger.info("✅ API server stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping API server: {e}")
                
        if self.agent_process:
            try:
                self.agent_process.terminate()
                self.agent_process.wait(timeout=10)
                logger.info("✅ Voice agent stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping voice agent: {e}")
    
    def start_system(self):
        """Start the complete voice agent system"""
        logger.info("🚀 SPIRITUAL VOICE AGENT SYSTEM STARTING")
        logger.info("=" * 60)
        
        # Check environment
        self.check_environment()
        
        # Start API server
        if not self.start_api_server():
            logger.error("💀 Failed to start API server - exiting")
            return False
            
        # Wait for API to be ready
        logger.info("⏱️ Waiting for API server to initialize...")
        time.sleep(8)
        
        # Start voice agent
        if not self.start_voice_agent():
            logger.error("💀 Failed to start voice agent - API only mode")
            # Continue running with just API server
        
        logger.info("=" * 60)
        logger.info("🎯 SPIRITUAL VOICE AGENT SYSTEM READY!")
        logger.info("💫 Available characters: Adina (compassionate), Raffa (wise)")
        logger.info(f"🌐 API available at: http://0.0.0.0:{self.port}")
        logger.info(f"📖 Documentation at: http://0.0.0.0:{self.port}/docs")
        logger.info("=" * 60)
        
        # Monitor processes
        self.monitor_processes()
        return True

def main():
    """Main entry point"""
    system = VoiceAgentSystem()
    
    try:
        success = system.start_system()
        if not success:
            sys.exit(1)
    except Exception as e:
        logger.error(f"💀 System startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()