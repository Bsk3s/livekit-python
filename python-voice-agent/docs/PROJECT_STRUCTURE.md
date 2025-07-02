# Project Structure

## Overview
This document outlines the clean, organized structure of the Spiritual Guidance Voice Agent project after comprehensive cleanup and refactoring.

## Directory Structure

```
python-voice-agent/
├── 📁 app/                          # Main application code
│   ├── 🔧 main.py                   # FastAPI application entry point
│   ├── 📁 agents/                   # LiveKit agent workers
│   │   ├── spiritual_worker.py      # Main agent worker implementation
│   │   ├── spiritual_session.py     # Session management logic
│   │   └── spiritual_agent.py       # Base agent functionality
│   ├── 📁 characters/               # Character definitions and personalities
│   │   ├── 👤 adina/               # Adina character (compassionate guide)
│   │   │   ├── agent.py            # Character-specific agent logic
│   │   │   ├── personality.py       # Personality prompts and behavior
│   │   │   └── voice_config.py      # Voice and TTS configuration
│   │   ├── 👤 raffa/               # Raffa character (wise mentor)
│   │   │   ├── agent.py            # Character-specific agent logic
│   │   │   ├── personality.py       # Personality prompts and behavior
│   │   │   └── voice_config.py      # Voice and TTS configuration
│   │   ├── base_character.py        # Base character interface
│   │   └── character_factory.py     # Character creation and management
│   ├── 📁 routes/                   # API route handlers
│   │   ├── health.py               # Health check endpoints
│   │   ├── token.py                # LiveKit token generation
│   │   └── websocket_audio.py       # WebSocket audio handlers
│   ├── 📁 services/                 # Core service implementations
│   │   ├── 🧠 llm/                 # Language model services
│   │   │   ├── base.py             # Abstract LLM interface
│   │   │   └── implementations/     # Concrete LLM implementations
│   │   │       └── openai.py       # OpenAI GPT integration
│   │   ├── 🎧 stt/                 # Speech-to-text services
│   │   │   ├── base.py             # Abstract STT interface
│   │   │   └── implementations/     # Concrete STT implementations
│   │   │       ├── deepgram.py     # Deepgram STT integration
│   │   │       └── direct_deepgram.py # Direct Deepgram implementation
│   │   ├── 🎙️ tts/                 # Text-to-speech services
│   │   │   └── base.py             # Abstract TTS interface
│   │   ├── base_service.py          # Base service interface
│   │   ├── deepgram_config.py       # Deepgram configuration
│   │   ├── livekit_token.py         # LiveKit token management
│   │   └── [various TTS services]   # TTS implementations
│   └── 📁 utils/                    # Utility functions
│       ├── character_utils.py       # Character-related utilities
│       └── logger.py               # Logging configuration
├── 📁 tests/                        # Test suites (organized)
│   ├── 📁 integration/             # Integration tests (23 files moved)
│   │   ├── test_audio_pipeline_fix.py
│   │   ├── test_elevenlabs_*.py     # ElevenLabs TTS tests
│   │   ├── test_deepgram_*.py       # Deepgram STT tests
│   │   └── [other integration tests]
│   ├── 📁 unit/                    # Unit tests
│   │   ├── 📁 characters/          # Character unit tests
│   │   └── 📁 services/            # Service unit tests
│   ├── conftest.py                 # Pytest configuration
│   └── requirements-test.txt        # Test-specific dependencies
├── 📁 docs/                        # Documentation
│   ├── API.md                      # API documentation
│   ├── DEPLOYMENT.md               # Deployment guide
│   └── PROJECT_STRUCTURE.md        # This file
├── 📁 scripts/                     # Deployment and utility scripts
│   ├── render.yaml                 # Render deployment config
│   ├── render-corrected.yaml       # Alternative deployment config
│   └── render-worker.yaml          # Worker-specific deployment config
├── 🚀 start_unified_service.py     # Main service entry point
├── 📋 requirements.txt             # Production dependencies
├── 📖 README.md                    # Project overview and quick start
├── 🔒 .gitignore                   # Git ignore patterns (comprehensive)
└── 🔧 .env.example                 # Environment variables template
```

## Code Metrics

- **Total Application Code:** ~3,849 lines
- **Test Files Moved:** 23 integration tests
- **Core Modules:** 
  - FastAPI application server
  - LiveKit agent worker
  - Character management system
  - Multi-service architecture (LLM, STT, TTS)

## Architecture Patterns

### 1. **Service Layer Pattern**
- Abstract base classes in `services/*/base.py`
- Concrete implementations in `services/*/implementations/`
- Dependency injection for service configuration

### 2. **Character Factory Pattern**
- Centralized character creation in `character_factory.py`
- Character-specific configurations isolated
- Extensible for new character additions

### 3. **Unified Service Entry Point**
- Single startup script (`start_unified_service.py`)
- Manages both API server and agent worker
- Production-ready process management

## Key Improvements Made

### 🧹 **Cleanup Achievements**
- ✅ Moved 23 test files from root to `tests/integration/`
- ✅ Removed duplicate `python-voice-agent/` directory
- ✅ Cleaned up log files and cache artifacts
- ✅ Organized deployment configs in `scripts/`
- ✅ Enhanced `.gitignore` with comprehensive patterns
- ✅ Created proper documentation structure

### 📚 **Documentation Added**
- ✅ Comprehensive README with setup instructions
- ✅ API documentation with endpoint specifications
- ✅ Deployment guide for production environments
- ✅ Project structure documentation
- ✅ Environment variables template

### 🏗️ **Structure Improvements**
- ✅ Logical directory organization
- ✅ Separation of concerns
- ✅ Clear module boundaries
- ✅ Proper test organization
- ✅ Configuration management

## Usage Guidelines

### For Developers
1. **New Features:** Add to appropriate service layer
2. **New Characters:** Use character factory pattern
3. **Testing:** Place unit tests in `tests/unit/`, integration in `tests/integration/`
4. **Documentation:** Update relevant docs in `docs/`

### For DevOps
1. **Deployment:** Use configs in `scripts/` directory
2. **Environment:** Copy `.env.example` to `.env` and configure
3. **Monitoring:** Use health endpoints and structured logging
4. **Scaling:** Consider LoadBalancer for multiple instances

## Next Steps

### Recommended Enhancements
1. **Add Rate Limiting** to API endpoints
2. **Implement Metrics Collection** for monitoring
3. **Add Database Layer** for user sessions (if needed)
4. **Enhanced Error Handling** with structured responses
5. **Performance Monitoring** and optimization

### Security Considerations
1. **API Key Management** - Rotate regularly
2. **Input Validation** - Sanitize all inputs
3. **Rate Limiting** - Prevent abuse
4. **Audit Logging** - Track usage patterns 