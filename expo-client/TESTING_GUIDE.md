# 🚀 Heavenly Hub Voice Agent - Testing Guide

## 🎯 Overview

This guide will help you test our **ULTRA-ADVANCED** voice agent with sub-300ms latency, Background Voice Cancellation, and multilingual turn detection on real mobile devices using Expo EAS Build.

## 🏗️ Build Types

### 1. 📱 Expo Go (Quick Development)
- **Best for**: Rapid UI testing and basic functionality
- **Limitations**: Cannot use native LiveKit features
- **Setup**: Instant - just scan QR code

### 2. 🔧 EAS Development Build (Recommended)
- **Best for**: Full feature testing with LiveKit voice agent
- **Features**: All native capabilities, hot reloading
- **Setup**: 10-15 minutes initial build

### 3. 🏭 EAS Preview Build (Production Testing)
- **Best for**: Final testing before app store submission
- **Features**: Production-like build without dev tools
- **Setup**: 15-20 minutes build time

## 🚀 Quick Start (Recommended Path)

### Step 1: Initial Setup
```bash
cd expo-client
chmod +x setup_eas.sh
./setup_eas.sh
```

### Step 2: Expo Login
```bash
npx expo login
```
*Create account at expo.dev if needed*

### Step 3: Initialize EAS Project
```bash
eas init
```
*This creates a unique project ID and configures EAS*

### Step 4: Build Development App
```bash
npm run build:dev
```
*Choose iOS or Android when prompted*

### Step 5: Install & Test
- Download the generated APK/IPA from the provided URL
- Install on your device
- Test voice conversations with Adina and Raffa!

## 📱 Detailed Testing Instructions

### 🎯 Testing Checklist

#### ✅ Pre-Testing Setup
- [ ] Expo account created and logged in
- [ ] EAS project initialized (`eas init` completed)
- [ ] Development build created and installed
- [ ] Device has microphone permissions enabled
- [ ] Stable internet connection (WiFi recommended)

#### ✅ Backend Connection Testing
- [ ] App loads without errors
- [ ] Character selection works (Adina/Raffa)
- [ ] "Connect" button responsive
- [ ] Token generation successful (check logs)

#### ✅ Voice Agent Features Testing
- [ ] **Voice Activity Detection**: App detects when you speak
- [ ] **Speech-to-Text**: Your words are transcribed accurately
- [ ] **LLM Response**: Agent provides spiritual guidance
- [ ] **Text-to-Speech**: Agent speaks with character voice
- [ ] **Character Voices**: Adina (gentle) vs Raffa (warm) distinct
- [ ] **Interruption Handling**: Can interrupt agent mid-speech
- [ ] **Turn Detection**: Natural conversation flow

#### ✅ Ultra-Advanced Features Validation
- [ ] **Sub-300ms Response**: Agent responds quickly (feels instant)
- [ ] **Background Noise Handling**: Works in noisy environments
- [ ] **Audio Quality**: Clear voice quality on both ends
- [ ] **Session Persistence**: Connection remains stable
- [ ] **Real-time Processing**: No noticeable delays

### 🎤 Voice Testing Scenarios

#### Scenario 1: Basic Spiritual Guidance
1. Connect to Adina
2. Say: "I'm feeling stressed about work"
3. Listen to compassionate response
4. Verify: Natural conversation flow, appropriate voice tone

#### Scenario 2: Character Switching
1. Test conversation with Adina
2. Disconnect and switch to Raffa
3. Ask the same question
4. Verify: Different personality and voice style

#### Scenario 3: Interruption Testing
1. Connect to either character
2. Ask a question that generates long response
3. Interrupt mid-sentence with new question
4. Verify: Smooth interruption handling, immediate response to new input

#### Scenario 4: Background Noise Testing
1. Test in quiet environment
2. Test with background music/TV
3. Test with other people talking
4. Verify: Background Voice Cancellation removes noise

#### Scenario 5: Extended Conversation
1. Have 5-10 minute conversation
2. Ask follow-up questions referencing earlier topics
3. Verify: Context memory and conversation continuity

## 🔧 Troubleshooting

### Common Issues & Solutions

#### "Failed to connect to room"
**Causes:**
- Backend server not running
- Network connectivity issues
- Invalid token generation

**Solutions:**
1. Check backend status: https://heavenly-new.onrender.com/health
2. Verify internet connection
3. Try switching between WiFi and cellular
4. Check device logs for specific error messages

#### "No audio input/output"
**Causes:**
- Microphone permissions not granted
- Audio session conflicts
- Device audio settings

**Solutions:**
1. Check app permissions in device settings
2. Restart the app
3. Test device microphone with other apps
4. Ensure device volume is up

#### "Token generation failed"
**Causes:**
- Backend server issues
- Invalid character selection
- Network timeout

**Solutions:**
1. Check backend health endpoint
2. Try different character (Adina/Raffa)
3. Wait and retry (server may be starting up)
4. Check device network settings

#### "App crashes on startup"
**Causes:**
- Incompatible build for device
- Missing dependencies
- Device compatibility issues

**Solutions:**
1. Rebuild with correct platform (iOS/Android)
2. Update Expo CLI and EAS CLI
3. Check device compatibility requirements
4. Try preview build instead of development build

### Performance Optimization

#### For Best Voice Quality:
- Use WiFi instead of cellular when possible
- Close other audio apps during testing
- Test in quiet environment initially
- Ensure device has sufficient battery (>20%)

#### For Debugging:
- Enable developer mode on device
- Use Chrome DevTools for React Native debugging
- Check Expo logs: `npx expo logs`
- Monitor backend logs on Render dashboard

## 📊 Performance Benchmarks

### Target Metrics (What to Expect):
- **First response latency**: <500ms from voice to voice
- **TTS first chunk**: <300ms (should feel instant)
- **Interruption response**: <400ms
- **Voice quality**: Clear, natural character voices
- **Background noise**: Significantly reduced with BVC

### Testing Performance:
1. Use stopwatch to measure response times
2. Test in various network conditions
3. Compare with/without background noise
4. Document any delays or quality issues

## 🎉 Success Criteria

Your testing is successful when:

✅ **Technical Performance**
- Sub-300ms TTS response times achieved
- Clear audio quality in both directions
- Stable connection for 10+ minute sessions
- Smooth interruption handling

✅ **User Experience**
- Natural conversation flow
- Distinct character personalities (Adina vs Raffa)
- Appropriate spiritual guidance responses
- Intuitive app interface

✅ **Advanced Features**
- Background noise effectively canceled
- Quick turn detection and response
- Context memory across conversation
- No audio artifacts or glitches

## 📱 Device Recommendations

### Recommended Test Devices:
- **iOS**: iPhone 12 or newer (iOS 15+)
- **Android**: Flagship devices (Android 10+)
- **RAM**: 4GB+ recommended
- **Storage**: 100MB+ available

### Network Requirements:
- **Bandwidth**: 1Mbps+ upload/download
- **Latency**: <200ms to servers
- **Stability**: Consistent connection

## 🔗 Resources

- **Expo Documentation**: https://docs.expo.dev/
- **EAS Build Guide**: https://docs.expo.dev/build/setup/
- **LiveKit React Native**: https://docs.livekit.io/client-sdks/react-native/
- **Backend API**: https://heavenly-new.onrender.com/
- **Backend Health**: https://heavenly-new.onrender.com/health

## 🆘 Support

If you encounter issues:

1. **Check Backend Health**: Visit https://heavenly-new.onrender.com/health
2. **Review Logs**: Use `npx expo logs` for debugging
3. **Test Network**: Verify internet connectivity
4. **Rebuild App**: Try fresh development build
5. **Contact Support**: Document specific error messages and steps to reproduce

---

## 🏆 Testing Achievement Levels

### 🥉 **Bronze Level**: Basic Functionality
- App loads and connects
- Basic voice interaction works
- Both characters accessible

### 🥈 **Silver Level**: Advanced Features  
- Sub-second response times
- Clear character voice distinction
- Interruption handling works

### 🥇 **Gold Level**: Ultra-Advanced Performance
- Sub-300ms response times achieved
- Background noise effectively canceled
- Perfect conversation flow
- Extended session stability

### 🏆 **Platinum Level**: Production Ready
- All features working flawlessly
- Consistent performance across devices
- Professional user experience
- Ready for app store submission

**Target: Achieve Gold/Platinum level performance! 🎯** 