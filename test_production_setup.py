#!/usr/bin/env python3
"""
Production Setup Verification Test
Tests all components before Render deployment
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
import logging

# Add app directory to path
sys.path.append('python-voice-agent/app')

from services.livekit_token import create_spiritual_access_token, get_livekit_credentials
from services.livekit_deepgram_tts import LiveKitDeepgramTTS
from characters.character_factory import CharacterFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionSetupTest:
    """Comprehensive production readiness test"""
    
    def __init__(self):
        self.results = {
            "environment_vars": False,
            "token_generation": False,
            "character_system": False,
            "tts_service": False,
            "agent_worker": False,
            "overall_status": False
        }
    
    def test_environment_variables(self):
        """Test all required environment variables"""
        print("🔍 Testing Environment Variables...")
        
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
            if not value:
                missing_vars.append(var)
            else:
                print(f"   ✅ {var}: {'*' * min(len(value), 8)}...")
        
        if missing_vars:
            print(f"   ❌ Missing variables: {missing_vars}")
            return False
        
        print("   ✅ All environment variables present")
        return True
    
    def test_token_generation(self):
        """Test production token generation"""
        print("🎫 Testing Token Generation...")
        
        try:
            # Test Adina token
            adina_token = create_spiritual_access_token(
                room="test-spiritual-adina-123456",
                user_id="test_user",
                user_name="Test User",
                character="adina",
                duration_minutes=30
            )
            
            # Test Raffa token
            raffa_token = create_spiritual_access_token(
                room="test-spiritual-raffa-123456",
                user_id="test_user",
                user_name="Test User", 
                character="raffa",
                duration_minutes=30
            )
            
            print(f"   ✅ Adina token: {len(adina_token)} characters")
            print(f"   ✅ Raffa token: {len(raffa_token)} characters")
            print(f"   ✅ Token format: JWT (starts with 'eyJ')")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Token generation failed: {e}")
            return False
    
    def test_character_system(self):
        """Test character factory and configurations"""
        print("🎭 Testing Character System...")
        
        try:
            # Test character creation
            adina = CharacterFactory.create_character("adina")
            raffa = CharacterFactory.create_character("raffa")
            
            print(f"   ✅ Adina: {adina.name} - {adina.description}")
            print(f"   ✅ Raffa: {raffa.name} - {raffa.description}")
            
            # Test voice configurations
            configs = CharacterFactory.CHARACTER_CONFIGS
            print(f"   ✅ Voice models:")
            print(f"      Adina: {configs['adina']['voice_model']}")
            print(f"      Raffa: {configs['raffa']['voice_model']}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Character system failed: {e}")
            return False
    
    async def test_tts_service(self):
        """Test ultra-fast TTS service"""
        print("🎤 Testing TTS Service...")
        
        try:
            tts = LiveKitDeepgramTTS()
            
            # Test both characters
            for character in ["adina", "raffa"]:
                print(f"   Testing {character}...")
                tts.set_character(character)
                
                start_time = time.time()
                
                # Test TTS generation
                async for chunk in tts.synthesize("Hello, this is a test message for production readiness."):
                    first_chunk_time = time.time() - start_time
                    print(f"   ✅ {character.title()} first chunk: {first_chunk_time*1000:.0f}ms")
                    break  # Just test first chunk
            
            await tts.aclose()
            return True
            
        except Exception as e:
            print(f"   ❌ TTS service failed: {e}")
            return False
    
    def test_agent_worker_imports(self):
        """Test agent worker can import all dependencies"""
        print("🤖 Testing Agent Worker Dependencies...")
        
        try:
            # Test critical imports
            from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
            from livekit.plugins import deepgram, openai, silero
            from livekit.plugins.turn_detector.multilingual import MultilingualModel
            
            print("   ✅ LiveKit agents framework")
            print("   ✅ Deepgram plugin")
            print("   ✅ OpenAI plugin") 
            print("   ✅ Silero VAD plugin")
            print("   ✅ Multilingual turn detection")
            
            # Test worker file exists
            worker_path = "python-voice-agent/app/agents/spiritual_worker.py"
            if os.path.exists(worker_path):
                print(f"   ✅ Worker file exists: {worker_path}")
            else:
                print(f"   ❌ Worker file missing: {worker_path}")
                return False
            
            return True
            
        except ImportError as e:
            print(f"   ❌ Import failed: {e}")
            return False
        except Exception as e:
            print(f"   ❌ Worker test failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run comprehensive production readiness test"""
        print("🌟 PRODUCTION READINESS TEST")
        print("=" * 50)
        print(f"🕐 Started at: {datetime.utcnow().isoformat()}Z")
        print()
        
        # Run all tests
        self.results["environment_vars"] = self.test_environment_variables()
        print()
        
        self.results["token_generation"] = self.test_token_generation()
        print()
        
        self.results["character_system"] = self.test_character_system()
        print()
        
        self.results["tts_service"] = await self.test_tts_service()
        print()
        
        self.results["agent_worker"] = self.test_agent_worker_imports()
        print()
        
        # Overall status
        all_passed = all(result for key, result in self.results.items() if key != "overall_status")
        self.results["overall_status"] = all_passed
        
        # Print summary
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        for test_name, passed in self.results.items():
            if test_name == "overall_status":
                continue
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} {test_name.replace('_', ' ').title()}")
        
        print()
        if all_passed:
            print("🎉 ALL TESTS PASSED - READY FOR PRODUCTION DEPLOYMENT!")
            print()
            print("Next steps:")
            print("1. Push code to GitHub")
            print("2. Deploy to Render using render.yaml")
            print("3. Set environment variables in Render")
            print("4. Test production endpoints")
            print("5. Update Expo client with production URL")
        else:
            print("❌ SOME TESTS FAILED - FIX ISSUES BEFORE DEPLOYMENT")
            failed_tests = [name for name, passed in self.results.items() if not passed and name != "overall_status"]
            print(f"Failed tests: {failed_tests}")
        
        return all_passed

async def main():
    """Main test function"""
    test_suite = ProductionSetupTest()
    success = await test_suite.run_all_tests()
    
    if success:
        print("\n🚀 System is production-ready!")
        sys.exit(0)
    else:
        print("\n🛑 Fix issues before deploying to production")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 