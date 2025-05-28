import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  Alert,
  StatusBar,
  Dimensions,
  Animated,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { Audio } from 'expo-av';
import {
  Room,
  connect,
  RoomEvent,
  RemoteParticipant,
  RemoteTrackPublication,
  RemoteTrack,
  Track,
  AudioTrack,
} from '@livekit/react-native';

const { width, height } = Dimensions.get('window');

export default function App() {
  const [room, setRoom] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [selectedCharacter, setSelectedCharacter] = useState('adina');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [pulseAnim] = useState(new Animated.Value(1));

  useEffect(() => {
    setupAudio();
    return () => {
      if (room) {
        room.disconnect();
      }
    };
  }, []);

  const setupAudio = async () => {
    try {
      await Audio.requestPermissionsAsync();
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        playThroughEarpieceAndroid: false,
        staysActiveInBackground: true,
      });
    } catch (error) {
      console.error('Error setting up audio:', error);
    }
  };

  const characters = {
    adina: {
      name: 'Adina',
      description: 'Compassionate Guide',
      color: ['#FFB6C1', '#FFC0CB', '#FFE4E1'],
      icon: 'heart-outline',
    },
    raffa: {
      name: 'Raffa',
      description: 'Wise Mentor',
      color: ['#87CEEB', '#B0E0E6', '#E0F6FF'],
      icon: 'library-outline',
    },
  };

  const connectToRoom = async () => {
    if (isConnecting) return;
    
    setIsConnecting(true);
    
    try {
      // Get token and WebSocket URL from backend
      const tokenData = await generateToken(selectedCharacter);
      
      const roomInstance = new Room();
      
      // Set up event listeners
      roomInstance.on(RoomEvent.Connected, () => {
        console.log('Connected to room');
        setIsConnected(true);
        setIsConnecting(false);
      });
      
      roomInstance.on(RoomEvent.Disconnected, () => {
        console.log('Disconnected from room');
        setIsConnected(false);
        setRoom(null);
      });
      
      roomInstance.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          setIsSpeaking(true);
          startPulseAnimation();
        }
      });
      
      roomInstance.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          setIsSpeaking(false);
          stopPulseAnimation();
        }
      });
      
      // Connect to room using WebSocket URL from backend
      await roomInstance.connect(tokenData.ws_url, tokenData.token);
      setRoom(roomInstance);
      
    } catch (error) {
      console.error('Failed to connect:', error);
      Alert.alert('Connection Error', 'Failed to connect to spiritual guidance session. Please check your internet connection and try again.');
      setIsConnecting(false);
    }
  };

  const generateToken = async (character) => {
    try {
      // Use production backend URL for iOS builds to avoid ATS issues
      const baseUrl = 'https://heavenly-new.onrender.com'; // Always use production for iOS
      
      console.log(`Generating token for ${character} using ${baseUrl}`);
      
      const response = await fetch(`${baseUrl}/api/generate-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          room: `spiritual-room-${character}`,
          identity: `user-${Date.now()}`,
          character: character,
        }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Token generation failed: ${response.status} - ${errorText}`);
      }
      
      const data = await response.json();
      console.log('Token generated successfully:', { 
        room: data.room, 
        character: data.character,
        hasToken: !!data.token,
        wsUrl: data.ws_url
      });
      
      return data; // Returns { token, room, character, ws_url }
    } catch (error) {
      console.error('Token generation error:', error);
      throw error;
    }
  };

  const disconnect = () => {
    if (room) {
      room.disconnect();
    }
  };

  const startPulseAnimation = () => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.2,
          duration: 800,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 800,
          useNativeDriver: true,
        }),
      ])
    ).start();
  };

  const stopPulseAnimation = () => {
    pulseAnim.stopAnimation();
    Animated.timing(pulseAnim, {
      toValue: 1,
      duration: 200,
      useNativeDriver: true,
    }).start();
  };

  const currentCharacter = characters[selectedCharacter];

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" />
      <LinearGradient
        colors={currentCharacter.color}
        style={styles.container}
      >
        <SafeAreaView style={styles.safeArea}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>Heavenly Hub</Text>
            <Text style={styles.subtitle}>Spiritual Voice Guidance</Text>
            <Text style={styles.buildInfo}>Ultra-Advanced Voice Agent - LiveKit Integration</Text>
          </View>

          {/* Character Selection */}
          <View style={styles.characterSection}>
            <Text style={styles.sectionTitle}>Choose Your Guide</Text>
            <View style={styles.characterButtons}>
              {Object.entries(characters).map(([key, char]) => (
                <TouchableOpacity
                  key={key}
                  style={[
                    styles.characterButton,
                    selectedCharacter === key && styles.selectedCharacter,
                  ]}
                  onPress={() => setSelectedCharacter(key)}
                  disabled={isConnected}
                >
                  <Ionicons
                    name={char.icon}
                    size={32}
                    color={selectedCharacter === key ? '#fff' : '#666'}
                  />
                  <Text
                    style={[
                      styles.characterName,
                      selectedCharacter === key && styles.selectedCharacterText,
                    ]}
                  >
                    {char.name}
                  </Text>
                  <Text
                    style={[
                      styles.characterDesc,
                      selectedCharacter === key && styles.selectedCharacterText,
                    ]}
                  >
                    {char.description}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Voice Interface */}
          <View style={styles.voiceSection}>
            <Animated.View
              style={[
                styles.voiceButton,
                { transform: [{ scale: pulseAnim }] },
                isSpeaking && styles.speakingButton,
              ]}
            >
              <TouchableOpacity
                style={styles.voiceButtonInner}
                onPress={isConnected ? disconnect : connectToRoom}
                disabled={isConnecting}
              >
                <Ionicons
                  name={
                    isConnected
                      ? 'stop-circle'
                      : isConnecting
                      ? 'hourglass'
                      : 'mic'
                  }
                  size={64}
                  color="#fff"
                />
              </TouchableOpacity>
            </Animated.View>

            <Text style={styles.voiceStatus}>
              {isConnecting
                ? 'Connecting to spiritual guidance...'
                : isConnected
                ? isSpeaking
                  ? `${currentCharacter.name} is speaking...`
                  : 'Tap to speak or listen'
                : `Connect to ${currentCharacter.name}`}
            </Text>
          </View>

          {/* Status */}
          <View style={styles.statusSection}>
            <View style={styles.statusItem}>
              <Ionicons
                name={isConnected ? 'checkmark-circle' : 'ellipse-outline'}
                size={20}
                color={isConnected ? '#4CAF50' : '#999'}
              />
              <Text style={styles.statusText}>
                {isConnected ? 'Connected - Voice Agent Active' : 'Ready to Connect'}
              </Text>
            </View>
          </View>
        </SafeAreaView>
      </LinearGradient>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
    paddingHorizontal: 20,
  },
  header: {
    alignItems: 'center',
    paddingVertical: 30,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
    textShadowColor: 'rgba(0,0,0,0.3)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 4,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.9)',
    marginTop: 5,
  },
  buildInfo: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 10,
    fontStyle: 'italic',
  },
  characterSection: {
    marginVertical: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
    marginBottom: 15,
    textAlign: 'center',
  },
  characterButtons: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  characterButton: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderRadius: 15,
    padding: 20,
    alignItems: 'center',
    width: width * 0.4,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  selectedCharacter: {
    backgroundColor: 'rgba(255,255,255,0.3)',
    borderColor: '#fff',
  },
  characterName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
    marginTop: 8,
  },
  characterDesc: {
    fontSize: 12,
    color: '#888',
    textAlign: 'center',
    marginTop: 4,
  },
  selectedCharacterText: {
    color: '#fff',
  },
  voiceSection: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  voiceButton: {
    width: 150,
    height: 150,
    borderRadius: 75,
    backgroundColor: 'rgba(255,255,255,0.3)',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  speakingButton: {
    backgroundColor: 'rgba(76, 175, 80, 0.8)',
  },
  voiceButtonInner: {
    width: '100%',
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
  },
  voiceStatus: {
    fontSize: 16,
    color: '#fff',
    marginTop: 20,
    textAlign: 'center',
    fontWeight: '500',
  },
  statusSection: {
    paddingBottom: 30,
  },
  statusItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusText: {
    fontSize: 14,
    color: '#fff',
    marginLeft: 8,
  },
}); 