# 🚀 Heavenly Hub Voice Agent - EAS Mobile App

## 🎯 Overview

This is an **ULTRA-ADVANCED** React Native mobile app built with Expo EAS Build that connects to our spiritual voice agent featuring:

- **Sub-300ms TTS Latency** with Deepgram Aura-2 voices
- **Background Voice Cancellation (BVC)** for noise removal  
- **Multilingual Turn Detection** for natural conversations
- **Character-Specific Voices**: Adina (gentle) and Raffa (wise)
- **Production-Ready Deployment** with automatic backend switching

## 🏗️ EAS Build Setup

### Prerequisites
- Node.js 18+ installed
- Expo account (create at [expo.dev](https://expo.dev))
- iOS device (for iOS testing) or Android device (for Android testing)
- Stable internet connection

### 1. Quick Setup
```bash
# Navigate to expo-client directory
cd expo-client

# Install dependencies
npm install --legacy-peer-deps

# Install EAS CLI globally
npm install -g eas-cli@latest

# Login to Expo
npx expo login

# Initialize EAS project
eas init
```

### 2. Build Options

#### 🔧 Development Build (Recommended)
Best for testing all features including LiveKit voice agent:
```bash
npm run build:dev
```
- Choose iOS or Android when prompted
- Supports all native features
- Includes debugging capabilities
- Hot reloading enabled

#### 🏭 Preview Build
Production-like standalone app:
```bash
npm run build:preview
```
- No Expo Go required
- Production environment
- Faster than development build

#### 🚀 Production Build
App store ready:
```bash
npm run build:production
```
- Optimized for distribution
- Ready for App Store/Play Store

### 3. Installation & Testing

1. **Wait for Build**: EAS will provide a URL when build completes (10-20 minutes)
2. **Download**: Get the APK (Android) or IPA (iOS) from the provided URL
3. **Install**: 
   - Android: Enable "Unknown Sources" and install APK
   - iOS: Use TestFlight or install via Xcode/Apple Configurator
4. **Test**: Launch app and test voice conversations!

## 🎭 App Features

### Character Selection
- **Adina**: Compassionate female guide with gentle voice (aura-2-luna-en)
- **Raffa**: Wise male mentor with warm voice (aura-2-orion-en)

### Voice Interface
- **Tap to Connect**: Connects to selected character
- **Real-time Voice**: Full-duplex voice conversation
- **Visual Feedback**: Pulsing animation when agent speaks
- **Smart Interruption**: Can interrupt agent mid-speech

### Technical Features
- **Automatic Backend Detection**: Switches between local/production
- **Token-Based Authentication**: Secure LiveKit room access
- **Real-time Audio Processing**: Low-latency voice pipeline
- **Background Voice Cancellation**: Removes environmental noise

## 🌐 Backend Configuration

### Automatic Environment Detection
The app automatically detects the environment:

- **Development** (`__DEV__ = true`): Uses local backend
  - Default: `http://192.168.1.100:8000`
  - Update IP in `App.js` for your local setup

- **Production** (`__DEV__ = false`): Uses production backend
  - URL: `https://heavenly-new.onrender.com`
  - Fully deployed on Render

### Local Backend Setup (Optional)
If testing with local backend:

1. **Find Your IP Address**:
   - Windows: `ipconfig`
   - Mac/Linux: `ifconfig`

2. **Update App.js**:
   ```javascript
   const baseUrl = __DEV__ 
     ? 'http://YOUR_IP_ADDRESS:8000' // Replace with your IP
     : 'https://heavenly-new.onrender.com';
   ```

3. **Start Local Backend**:
   ```bash
   cd ../python-voice-agent
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## 🧪 Testing Guide

### Pre-Testing Checklist
- [ ] EAS build completed and installed
- [ ] Device microphone permissions granted
- [ ] Stable internet connection (WiFi recommended)
- [ ] Backend health verified (if using production)

### Backend Health Check
```bash
# Test production backend
curl https://heavenly-new.onrender.com/health

# Expected response:
{
  "status": "healthy",
  "service": "Heavenly Hub Voice Agent API",
  "version": "1.0.0",
  "timestamp": "2024-..."
}
```

### Voice Testing Scenarios

#### Basic Functionality Test
1. Launch app
2. Select character (Adina or Raffa)
3. Tap "Connect" button
4. Say: "Hello, I need spiritual guidance"
5. Verify: Agent responds with character voice

#### Advanced Features Test
1. **Interruption**: Interrupt agent mid-sentence
2. **Background Noise**: Test with music/TV playing
3. **Extended Conversation**: 5+ minute conversation
4. **Character Switching**: Test both Adina and Raffa
5. **Context Memory**: Reference earlier conversation topics

### Performance Benchmarks
Target metrics to verify:
- **Response Latency**: <500ms voice-to-voice
- **Audio Quality**: Clear, natural voices
- **Connection Stability**: No drops during conversation
- **Interruption Speed**: <400ms response to interruption

## 🔧 Troubleshooting

### Common Issues

#### "Failed to connect to room"
- **Check internet connection**
- **Verify backend health**: Visit production health endpoint
- **Try switching WiFi/cellular**
- **Wait if backend is starting up** (Render free tier sleeps)

#### "No audio input/output"
- **Check microphone permissions** in device settings
- **Restart the app**
- **Test device audio** with other apps
- **Ensure volume is up**

#### "Token generation failed"
- **Backend server might be sleeping** (wait 30 seconds)
- **Try different character** (Adina/Raffa)
- **Check device network settings**
- **Verify backend URL in logs**

#### "App won't install"
- **Android**: Enable "Unknown Sources" in security settings
- **iOS**: Install via TestFlight or developer certificate
- **Check device compatibility** (Android 10+/iOS 15+)

### Performance Issues
- **Use WiFi instead of cellular** for best quality
- **Close other audio apps** during testing
- **Ensure device battery >20%**
- **Test in quiet environment first**

### Debugging
```bash
# View app logs
npx expo logs

# Test backend connectivity
node test_backend.js

# Check build status
eas build:list
```

## 📊 Build Configurations

### Development Profile
```json
{
  "developmentClient": true,
  "distribution": "internal",
  "ios": { "resourceClass": "m-medium" },
  "android": { "gradleCommand": ":app:assembleDebug" }
}
```

### Preview Profile
```json
{
  "distribution": "internal",
  "ios": { "resourceClass": "m-medium" },
  "android": { "buildType": "apk" }
}
```

### Production Profile
```json
{
  "ios": { "resourceClass": "m-medium" },
  "android": { "resourceClass": "medium" }
}
```

## 🎯 Success Criteria

Your EAS app is successfully working when:

✅ **Installation**
- App installs without errors
- Launches and shows character selection
- No crash on startup

✅ **Connection**
- Successfully connects to backend
- Token generation works
- LiveKit room connection established

✅ **Voice Features**
- Voice input detected and transcribed
- Agent responds with character voice
- Interruption handling works smoothly
- Background noise effectively reduced

✅ **Performance**
- Sub-500ms response times
- Clear audio quality both directions
- Stable 10+ minute conversations
- Natural conversation flow

## 🔗 Resources

- **Expo EAS Build**: https://docs.expo.dev/build/
- **LiveKit React Native**: https://docs.livekit.io/client-sdks/react-native/
- **Backend API**: https://heavenly-new.onrender.com/
- **Health Check**: https://heavenly-new.onrender.com/health

## 🚀 Quick Commands

```bash
# Setup
npm install --legacy-peer-deps
npx expo login
eas init

# Build
npm run build:dev        # Development build
npm run build:preview    # Preview build  
npm run build:production # Production build

# Debug
npx expo logs           # View logs
node test_backend.js    # Test backend
eas build:list         # Check builds

# Development
npx expo start         # Start dev server
npx expo start --android  # Android dev
npx expo start --ios      # iOS dev
```

## 🎉 Next Steps

1. **Complete EAS Setup**: Follow quick setup instructions
2. **Build Development App**: `npm run build:dev`
3. **Install on Device**: Download and install APK/IPA
4. **Test Voice Agent**: Have conversations with Adina and Raffa
5. **Verify Performance**: Check sub-300ms response times
6. **Report Issues**: Document any problems for improvement

**Ready to test the highest-level voice agent technology! 🚀** 