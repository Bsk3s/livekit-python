#!/bin/bash

echo "🚀 HEAVENLY HUB VOICE AGENT - EAS SETUP"
echo "======================================="
echo

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Please run this script from the expo-client directory"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed. Please install Node.js first."
    exit 1
fi

echo "📦 Installing dependencies..."
npm install

echo "🔧 Installing EAS CLI globally..."
npm install -g @expo/cli@latest
npm install -g eas-cli@latest

echo "✅ Dependencies installed successfully!"
echo

echo "🎯 EAS SETUP INSTRUCTIONS:"
echo "=========================="
echo

echo "1. 📱 LOGIN TO EXPO:"
echo "   Run: npx expo login"
echo "   (Use your Expo account or create one at expo.dev)"
echo

echo "2. 🏗️ INITIALIZE EAS PROJECT:"
echo "   Run: eas init"
echo "   This will:"
echo "   - Create a new project ID"
echo "   - Update app.json with project ID"
echo "   - Configure EAS settings"
echo

echo "3. 🔧 CONFIGURE BUILDS:"
echo "   The eas.json file is already configured with:"
echo "   • Development build (for testing with Expo Go)"
echo "   • Preview build (standalone APK/IPA)"
echo "   • Production build (for app stores)"
echo

echo "4. 🏭 BUILD COMMANDS:"
echo "   Development: npm run build:dev"
echo "   Preview:     npm run build:preview"
echo "   Production:  npm run build:production"
echo

echo "5. 📱 TESTING OPTIONS:"
echo

echo "   A. EXPO GO (Quickest for development):"
echo "      - Run: npx expo start"
echo "      - Scan QR code with Expo Go app"
echo "      - Limited to Expo SDK features only"
echo

echo "   B. EAS DEVELOPMENT BUILD (Full features):"
echo "      - Run: npm run build:dev"
echo "      - Install the generated APK/IPA on device"
echo "      - Supports all native features (LiveKit, etc.)"
echo

echo "   C. EAS PREVIEW BUILD (Production-like):"
echo "      - Run: npm run build:preview"
echo "      - Generates standalone app for testing"
echo "      - No Expo Go required"
echo

echo "6. 🌐 BACKEND CONFIGURATION:"
echo "   The app automatically detects:"
echo "   • Development: Uses local IP (192.168.1.100:8000)"
echo "   • Production: Uses https://heavenly-new.onrender.com"
echo

echo "7. 🔧 IP ADDRESS SETUP:"
echo "   For local testing, update the IP address in App.js:"
echo "   • Find your computer's IP: ipconfig (Windows) or ifconfig (Mac/Linux)"
echo "   • Replace 192.168.1.100 with your actual IP"
echo

echo "8. 📋 REQUIRED STEPS:"
echo "   □ Run: npx expo login"
echo "   □ Run: eas init"
echo "   □ Update IP address in App.js (for local testing)"
echo "   □ Choose build type and run build command"
echo "   □ Install generated app on device"
echo "   □ Test voice agent functionality"
echo

echo "🎉 EAS SETUP COMPLETE!"
echo

echo "🚀 QUICK START:"
echo "==============="
echo "1. npx expo login"
echo "2. eas init"
echo "3. npm run build:dev"
echo "4. Install APK/IPA on device"
echo "5. Test with Adina or Raffa!"
echo

echo "📖 For detailed instructions, see: https://docs.expo.dev/build/setup/"
echo 