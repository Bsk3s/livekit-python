const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Add resolver configuration for LiveKit
config.resolver.alias = {
  ...config.resolver.alias,
  'react-native-webrtc': '@livekit/react-native-webrtc',
};

// Add platform extensions
config.resolver.platforms = ['ios', 'android', 'native', 'web'];

// Configure transformer for better compatibility
config.transformer.minifierConfig = {
  keep_fnames: true,
  mangle: {
    keep_fnames: true,
  },
};

module.exports = config; 