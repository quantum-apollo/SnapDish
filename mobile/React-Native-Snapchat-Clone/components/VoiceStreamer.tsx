
import { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Switch, Platform } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useAudioRecorder, RecordingPresets } from 'expo-audio';
import Constants from 'expo-constants';

// Use EAS secret for backend URL
// Set your production backend URLs in app.json (extra) or EAS secrets
const WS_URL = Constants.expoConfig?.extra?.BACKEND_WS_URL || process.env.BACKEND_WS_URL || 'wss://your-production-backend.com/v1/voice/stream';
const VOICE_API_URL = Constants.expoConfig?.extra?.BACKEND_VOICE_URL || process.env.BACKEND_VOICE_URL || 'https://your-production-backend.com/v1/voice';




export default function VoiceStreamer({ onTranscript, onError }: {
  onTranscript?: (text: string) => void;
  onError?: (err: Error) => void;
}) {
  const ws = useRef<WebSocket | null>(null);

  // Use Expo's built-in HIGH_QUALITY preset for standards compliance
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [streamingMode, setStreamingMode] = useState(false); // false = voice message, true = real-time
  const [recordingError, setRecordingError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      ws.current?.close();
    };
  }, []);

  // Real-time streaming logic (PCM chunk streaming)
  const handleStartStreaming = async () => {
    setRecordingError(null);
    try {
      ws.current = new WebSocket(WS_URL);
      ws.current.binaryType = 'arraybuffer';
      ws.current.onopen = async () => {
        try {
          await recorder.prepareToRecordAsync();
          recorder.record();
          // Optionally, you can use a polling or event-based system to get PCM chunks if supported
        } catch (err) {
          setRecordingError((err as Error).message || String(err));
          if (onError) onError(err as Error);
        }
      };
      ws.current.onmessage = (event) => {
        if (onTranscript) onTranscript(event.data);
        // Optionally: handle streaming audio response here
      };
      ws.current.onerror = (e) => {
        setRecordingError('WebSocket error');
        if (onError) onError(new Error('WebSocket error'));
      };
    } catch (err) {
      setRecordingError((err as Error).message || String(err));
      if (onError) onError(err as Error);
    }
  };

  // Voice message logic (record, then send whole file)
  const handleStartMessage = async () => {
    setRecordingError(null);
    try {
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch (err) {
      setRecordingError((err as Error).message || String(err));
      if (onError) onError(err as Error);
    }
  };

  const handleStop = async () => {
    setRecordingError(null);
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (streamingMode) {
        ws.current?.send('END');
        ws.current?.close();
      } else {
        if (uri) {
          const response = await fetch(uri);
          const blob = await response.blob();
          // Send blob to backend (POST /v1/voice)
          const formData = new FormData();
          formData.append('audio', blob, 'voice.m4a');
          await fetch(VOICE_API_URL, {
            method: 'POST',
            body: formData,
          });
        }
      }
    } catch (err) {
      setRecordingError((err as Error).message || String(err));
      if (onError) onError(err as Error);
    }
  };

  return (
    <View style={styles.container}>
      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 8 }}>
        <Text style={{ marginRight: 8, color: '#222', fontSize: 14 }}>Voice Msg</Text>
        <Switch
          value={streamingMode}
          onValueChange={setStreamingMode}
          thumbColor={streamingMode ? '#FF6B6B' : '#ccc'}
          trackColor={{ false: '#eee', true: '#FF6B6B' }}
        />
        <Text style={{ marginLeft: 8, color: '#222', fontSize: 14 }}>Real-Time</Text>
      </View>
      <TouchableOpacity
        style={[styles.micButton, recorder.isRecording && styles.micButtonActive]}
        onPress={recorder.isRecording ? handleStop : (streamingMode ? handleStartStreaming : handleStartMessage)}
        accessibilityLabel={recorder.isRecording ? 'Stop recording' : 'Start recording'}
        activeOpacity={0.7}
      >
        <MaterialCommunityIcons
          name={recorder.isRecording ? 'microphone' : 'microphone-outline'}
          size={36}
          color={recorder.isRecording ? '#fff' : '#FF6B6B'}
        />
        {recorder.isRecording && (
          <ActivityIndicator style={styles.recordingIndicator} color="#fff" size="small" />
        )}
      </TouchableOpacity>
      {/* Optionally show status or error */}
      {recordingError && (
        <Text style={{ color: 'red', marginTop: 8 }}>{recordingError}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginVertical: 12, alignItems: 'center', justifyContent: 'center' },
  micButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#FF6B6B',
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
    marginBottom: 4,
  },
  micButtonActive: {
    backgroundColor: '#FF6B6B',
    borderColor: '#FF6B6B',
  },
  recordingIndicator: {
    position: 'absolute',
    right: 10,
    bottom: 10,
  },
});
