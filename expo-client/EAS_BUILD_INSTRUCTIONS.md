# 🚀 EAS Build Instructions - Heavenly Hub Voice Agent

## 🎯 Quick Start Guide

Follow these exact steps to build and test the **ULTRA-ADVANCED** voice agent on your mobile device.

## ⚡ Step-by-Step Instructions

### 1. Login to Expo
```bash
npx expo login
```
*Create account at expo.dev if you don't have one*

### 2. Initialize EAS Project
```bash
eas init
```
*This will:*
- Create a unique project ID
- Update app.json with the project ID
- Configure EAS settings

### 3. Build Development App
```bash
npm run build:dev
```
*Choose your platform:*
- Select **iOS** if you have an iPhone/iPad
- Select **Android** if you have an Android device

### 4. Wait for Build (10-20 minutes)
The build will:
- Upload your code to Expo servers
- Compile native iOS/Android app
- Generate downloadable APK/IPA file
- Provide download URL when complete

### 5. Install on Device

#### For Android:
1. Download APK from provided URL
2. Enable "Unknown Sources" in device settings
3. Install APK file
4. Grant microphone permissions when prompted

#### For iOS:
1. Download IPA from provided URL
2. Install via TestFlight (if distributed) or Xcode
3. Trust developer certificate in Settings
4. Grant microphone permissions when prompted

### 6. Test Voice Agent
1. Launch "Heavenly Hub Voice Agent" app
2. Select character: **Adina** (gentle) or **Raffa** (wise)
3. Tap **Connect** button
4. Say: *"Hello, I need some spiritual guidance"*
5. Listen to character response with unique voice!

## 🎯 What You're Testing

### Ultra-Advanced Features:
- ✅ **Sub-300ms TTS Latency** (should feel instant)
- ✅ **Background Voice Cancellation** (works in noisy environments)
- ✅ **Multilingual Turn Detection** (natural conversation flow)
- ✅ **Character-Specific Voices** (Adina vs Raffa sound different)
- ✅ **Smart Interruption** (can interrupt agent mid-speech)
- ✅ **Context Memory** (remembers conversation topics)

### Performance Targets:
- **Response Time**: <500ms voice-to-voice
- **Audio Quality**: Clear, natural character voices
- **Connection**: Stable for 10+ minute conversations
- **Interruption**: <400ms response when you interrupt

## 🔧 Troubleshooting

### Build Issues
```bash
# If build fails, try:
eas build:list          # Check build status
eas build --clear-cache # Clear build cache
npm run build:preview   # Try preview build instead
```

### Connection Issues
- **Backend sleeping**: Wait 30 seconds and try again
- **Network**: Use WiFi instead of cellular
- **Permissions**: Grant microphone access in device settings

### Audio Issues
- **No sound**: Check device volume and audio permissions
- **Poor quality**: Test in quiet environment first
- **No input**: Verify microphone works in other apps

## 📱 Test Scenarios

### Scenario 1: Basic Spiritual Guidance
1. Connect to **Adina**
2. Say: *"I'm feeling stressed about work"*
3. Verify: Compassionate response with gentle female voice

### Scenario 2: Character Comparison
1. Test conversation with **Adina**
2. Disconnect and switch to **Raffa**
3. Ask similar question
4. Verify: Different personality and male voice

### Scenario 3: Advanced Features
1. **Interruption Test**: Interrupt agent mid-sentence
2. **Background Noise**: Test with TV/music playing
3. **Extended Chat**: Have 5+ minute conversation
4. **Context Memory**: Reference earlier topics

## 🎉 Success Indicators

You'll know it's working when:
- ✅ App connects without errors
- ✅ You hear distinct character voices (Adina gentle, Raffa wise)
- ✅ Agent responds quickly (<1 second)
- ✅ You can interrupt and get immediate response
- ✅ Conversation feels natural and fluid
- ✅ Background noise doesn't interfere

## 🚀 Alternative Build Options

### Preview Build (if Development fails)
```bash
npm run build:preview
```
- Faster build time
- No development features
- Production-like environment

### Production Build (final testing)
```bash
npm run build:production
```
- App store ready
- Optimized performance
- Maximum stability

## 📊 Backend Status

The app automatically connects to:
- **Production**: `https://heavenly-new.onrender.com` (may take 30s to wake up)
- **Development**: Your local IP (if __DEV__ = true)

Check backend health:
```bash
curl https://heavenly-new.onrender.com/health
```

## 🆘 Need Help?

### Common Commands
```bash
# Check build status
eas build:list

# View app logs  
npx expo logs

# Test backend
node test_backend.js

# Start development server
npx expo start
```

### Resources
- **EAS Build Docs**: https://docs.expo.dev/build/
- **LiveKit React Native**: https://docs.livekit.io/client-sdks/react-native/
- **Backend Health**: https://heavenly-new.onrender.com/health

## 🏆 Achievement Goal

**Target**: Test the **HIGHEST LEVEL** voice agent with:
- Enterprise-grade Background Voice Cancellation
- Sub-300ms response times
- Natural conversation flow
- Production-ready performance

**This represents the cutting edge of voice AI technology available today! 🚀**

---

## 📋 Quick Checklist

- [ ] `npx expo login` completed
- [ ] `eas init` completed  
- [ ] `npm run build:dev` started
- [ ] Build completed (10-20 min wait)
- [ ] App downloaded and installed
- [ ] Microphone permissions granted
- [ ] Successfully connected to voice agent
- [ ] Tested both Adina and Raffa characters
- [ ] Verified sub-500ms response times
- [ ] Tested interruption handling
- [ ] Achieved natural conversation flow

**Ready to experience the future of voice AI! 🎯** 