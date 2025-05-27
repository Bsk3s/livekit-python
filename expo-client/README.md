# Heavenly Hub Voice Agent - Expo Client

A beautiful React Native client for testing your spiritual voice agent with real mobile devices.

## Features

- 🎤 **Real Voice Testing**: Test actual voice input/output on mobile devices
- 👥 **Character Selection**: Choose between Adina (compassionate guide) and Raffa (wise mentor)
- 🎨 **Beautiful UI**: Modern gradient design with character-specific themes
- 📱 **Cross-Platform**: Works on iOS, Android, and web
- 🔊 **Audio Permissions**: Automatic microphone and audio setup
- 📡 **LiveKit Integration**: Direct connection to your voice agent backend

## Quick Start

### 1. Install Dependencies

```bash
cd expo-client
npm install
```

### 2. Install Expo CLI (if not already installed)

```bash
npm install -g @expo/cli
```

### 3. Update Configuration

Edit `App.js` and update the server URL:

```javascript
// Replace this line in the generateToken function:
const response = await fetch('http://localhost:8000/api/generate-token', {
// With your actual server URL:
const response = await fetch('http://YOUR_SERVER_IP:8000/api/generate-token', {
```

**Important**: Use your computer's IP address, not `localhost`, so your mobile device can reach the server.

### 4. Start Your Backend

Make sure your Python voice agent is running:

```bash
cd ../python-voice-agent
source venv311/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Start LiveKit Agent

In another terminal:

```bash
cd python-voice-agent
source venv311/bin/activate
python app/agents/spiritual_session.py dev
```

### 6. Start Expo Development Server

```bash
npm start
```

### 7. Test on Device

- **iOS**: Scan QR code with Camera app
- **Android**: Scan QR code with Expo Go app
- **Web**: Press 'w' in terminal

## Environment Setup

### Backend Environment Variables

Make sure your `python-voice-agent/.env` includes:

```env
# LiveKit Configuration
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_WS_URL=ws://YOUR_SERVER_IP:7880

# Voice Services
DEEPGRAM_API_KEY=your_deepgram_key
OPENAI_API_KEY=your_openai_key
```

### Finding Your Server IP

**macOS/Linux**:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

**Windows**:
```cmd
ipconfig
```

Look for your local network IP (usually starts with 192.168.x.x or 10.x.x.x).

## Testing Flow

1. **Select Character**: Choose Adina or Raffa
2. **Connect**: Tap the microphone button to connect
3. **Speak**: Talk naturally to your spiritual guide
4. **Listen**: Hear responses with character-specific voices
5. **Interrupt**: Test interruption by speaking while the agent is talking

## Character Voices

- **Adina**: Luna voice (gentle, soothing female)
- **Raffa**: Orion voice (warm, approachable male)

## Troubleshooting

### Connection Issues

1. **Check Network**: Ensure phone and computer are on same WiFi
2. **Check IP**: Use actual IP address, not localhost
3. **Check Ports**: Ensure ports 8000 and 7880 are accessible
4. **Check Backend**: Verify FastAPI server is running on 0.0.0.0:8000

### Audio Issues

1. **Permissions**: Grant microphone permissions when prompted
2. **Audio Mode**: App automatically configures audio for voice calls
3. **Volume**: Ensure device volume is up
4. **Headphones**: Test with and without headphones

### Performance Issues

1. **Network**: Use strong WiFi connection
2. **Device**: Close other apps for better performance
3. **Background**: Keep app in foreground during testing

## Development

### Adding New Characters

1. Update `characters` object in `App.js`
2. Add character configuration in backend
3. Update voice models in Deepgram TTS service

### Customizing UI

- Modify gradient colors in character definitions
- Update styles in `StyleSheet.create()`
- Add new animations or visual feedback

### Testing Features

- **Voice Activity**: Visual feedback when speaking/listening
- **Connection Status**: Real-time connection indicators
- **Character Switching**: Test different personalities
- **Interruption**: Natural conversation flow

## Production Considerations

1. **Security**: Implement proper token validation
2. **CORS**: Restrict origins to your app's domain
3. **Rate Limiting**: Add API rate limiting
4. **Error Handling**: Improve error messages and recovery
5. **Analytics**: Add usage tracking and performance monitoring

## Next Steps

- Test voice quality and latency
- Verify character personalities work correctly
- Test interruption handling
- Validate on different devices and network conditions
- Gather user feedback for improvements 