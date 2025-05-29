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
import { registerGlobals } from '@livekit/react-native';
import {
  Room,
  RoomEvent,
  Track,
} from 'livekit-client';

// Register LiveKit globals for React Native
registerGlobals();

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
      await roomInstance.connect(tokenData.wsUrl, tokenData.token);
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
        wsUrl: data.wsUrl
      });
      
      return data; // Returns { token, room, character, wsUrl }
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
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
      >
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.header}>
            <Text style={styles.title}>Heavenly Hub</Text>
            <Text style={styles.subtitle}>Voice Agent</Text>
          </View>

          <View style={styles.characterSelection}>
            <Text style={styles.sectionTitle}>Choose Your Guide</Text>
            <View style={styles.characterButtons}>
              {Object.entries(characters).map(([key, character]) => (
                <TouchableOpacity
                  key={key}
                  style={[
                    styles.characterButton,
                    selectedCharacter === key && styles.selectedCharacter,
                  ]}
                  onPress={() => setSelectedCharacter(key)}
                  disabled={isConnected || isConnecting}
                >
                  <Ionicons
                    name={character.icon}
                    size={32}
                    color={selectedCharacter === key ? '#fff' : '#666'}
                  />
                  <Text
                    style={[
                      styles.characterName,
                      selectedCharacter === key && styles.selectedCharacterText,
                    ]}
                  >
                    {character.name}
                  </Text>
                  <Text
                    style={[
                      styles.characterDescription,
                      selectedCharacter === key && styles.selectedCharacterText,
                    ]}
                  >
                    {character.description}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <View style={styles.connectionSection}>
            <Animated.View
              style={[
                styles.connectionIndicator,
                {
                  transform: [{ scale: isSpeaking ? pulseAnim : 1 }],
                  backgroundColor: isConnected
                    ? isSpeaking
                      ? '#4CAF50'
                      : '#2196F3'
                    : '#9E9E9E',
                },
              ]}
            >
              <Ionicons
                name={
                  isConnected
                    ? isSpeaking
                      ? 'volume-high'
                      : 'mic'
                    : 'mic-off'
                }
                size={48}
                color="#fff"
              />
            </Animated.View>

            <Text style={styles.statusText}>
              {isConnecting
                ? 'Connecting to spiritual guidance...'
                : isConnected
                ? isSpeaking
                  ? `${currentCharacter.name} is speaking...`
                  : `Connected to ${currentCharacter.name}`
                : 'Ready to connect'}
            </Text>

            <TouchableOpacity
              style={[
                styles.connectButton,
                isConnected && styles.disconnectButton,
                isConnecting && styles.connectingButton,
              ]}
              onPress={isConnected ? disconnect : connectToRoom}
              disabled={isConnecting}
            >
              <Text style={styles.connectButtonText}>
                {isConnecting
                  ? 'Connecting...'
                  : isConnected
                  ? 'End Session'
                  : 'Begin Spiritual Guidance'}
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>
              Experience real-time spiritual guidance with AI companions
            </Text>
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
    paddingTop: 20,
    paddingBottom: 30,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
    textShadowColor: 'rgba(0, 0, 0, 0.3)',
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 4,
  },
  subtitle: {
    fontSize: 18,
    color: '#fff',
    opacity: 0.9,
    marginTop: 5,
  },
  characterSelection: {
    marginBottom: 40,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#fff',
    textAlign: 'center',
    marginBottom: 20,
    textShadowColor: 'rgba(0, 0, 0, 0.3)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  characterButtons: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  characterButton: {
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    borderRadius: 15,
    padding: 20,
    alignItems: 'center',
    width: width * 0.4,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  selectedCharacter: {
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
    borderColor: '#fff',
  },
  characterName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#666',
    marginTop: 10,
  },
  characterDescription: {
    fontSize: 14,
    color: '#666',
    marginTop: 5,
    textAlign: 'center',
  },
  selectedCharacterText: {
    color: '#fff',
  },
  connectionSection: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  connectionIndicator: {
    width: 120,
    height: 120,
    borderRadius: 60,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 30,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  statusText: {
    fontSize: 18,
    color: '#fff',
    textAlign: 'center',
    marginBottom: 30,
    paddingHorizontal: 20,
    textShadowColor: 'rgba(0, 0, 0, 0.3)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  connectButton: {
    backgroundColor: '#fff',
    paddingHorizontal: 40,
    paddingVertical: 15,
    borderRadius: 25,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  disconnectButton: {
    backgroundColor: '#FF5722',
  },
  connectingButton: {
    backgroundColor: '#FFC107',
  },
  connectButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    textAlign: 'center',
  },
  footer: {
    paddingBottom: 20,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 14,
    color: '#fff',
    opacity: 0.8,
    textAlign: 'center',
    textShadowColor: 'rgba(0, 0, 0, 0.3)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
}); 