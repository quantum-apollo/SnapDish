import { useEffect, useRef, useState } from 'react';
import { View, Alert } from 'react-native';
import { useAudioRecorder, useAudioPlayer, IOSOutputFormat, AudioQuality } from 'expo-audio';
import type { RecordingOptions } from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import { voice } from '@/src/api/client';
import { FAB, Text, useTheme } from 'react-native-paper';

// Records 16kHz mono LINEAR PCM → produces a WAV file the backend can decode as int16 PCM
const PCM_RECORDING_OPTIONS: RecordingOptions = {
  extension: '.wav',
  sampleRate: 16000,
  numberOfChannels: 1,
  bitRate: 256000,
  ios: {
    extension: '.wav',
    outputFormat: IOSOutputFormat.LINEARPCM,
    audioQuality: AudioQuality.HIGH,
    sampleRate: 16000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  android: {
    extension: '.wav',
    outputFormat: 'default',
    audioEncoder: 'default',
    sampleRate: 16000,
  },
  web: {},
};

/**
 * Parse a WAV ArrayBuffer and extract the raw PCM data + sample rate.
 * Walks RIFF chunks to find the "data" chunk, rather than assuming 44-byte offset.
 */
function stripWavHeaderFromBuffer(buf: ArrayBuffer): { pcmBase64: string; sampleRate: number } {
  const bytes = new Uint8Array(buf);
  const view = new DataView(buf);
  let sampleRate = 16000;
  if (bytes.length > 28) sampleRate = view.getUint32(24, true);
  let dataOffset = 44; // safe fallback
  let offset = 12;
  while (offset + 8 <= bytes.length) {
    const id = String.fromCharCode(bytes[offset], bytes[offset + 1], bytes[offset + 2], bytes[offset + 3]);
    const size = view.getUint32(offset + 4, true);
    if (id === 'data') { dataOffset = offset + 8; break; }
    offset += 8 + size + (size % 2 !== 0 ? 1 : 0);
  }
  const pcmBytes = bytes.slice(dataOffset);
  let binary = '';
  for (let i = 0; i < pcmBytes.length; i++) binary += String.fromCharCode(pcmBytes[i]);
  return { pcmBase64: btoa(binary), sampleRate };
}

/** Wrap raw PCM int16 base64 in a RIFF WAV container, returning Uint8Array bytes. */
function buildWavBytes(pcmBase64: string, sampleRate: number): Uint8Array {
  const pcmBinary = atob(pcmBase64);
  const dataSize = pcmBinary.length;
  const out = new Uint8Array(44 + dataSize);
  const view = new DataView(out.buffer);
  const w = (o: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  w(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  w(8, 'WAVE');
  w(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);           // PCM
  view.setUint16(22, 1, true);           // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byteRate
  view.setUint16(32, 2, true);           // blockAlign
  view.setUint16(34, 16, true);          // bitsPerSample
  w(36, 'data');
  view.setUint32(40, dataSize, true);
  for (let i = 0; i < pcmBinary.length; i++) out[44 + i] = pcmBinary.charCodeAt(i);
  return out;
}

interface VoiceStreamerProps {
  onTranscript?: (text: string) => void;
  onError?: (err: Error) => void;
}

/**
 * VoiceStreamer — Bidirectional conversational AI voice component.
 * User speaks → 16kHz PCM sent to /v1/voice → Chef Marco's PCM response played back.
 * Enables back-and-forth voice conversation with multimodal Chef Marco AI.
 */
export default function VoiceStreamer({ onTranscript, onError }: VoiceStreamerProps) {
  const recorder = useAudioRecorder(PCM_RECORDING_OPTIONS);
  const player = useAudioPlayer();
  const [isActive, setIsActive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [statusText, setStatusText] = useState('Tap to speak with Chef Marco');
  const tempFileRef = useRef<File | null>(null);

  // Clean up cached response audio on unmount
  useEffect(() => {
    return () => {
      try { tempFileRef.current?.delete(); } catch { /* ignore */ }
    };
  }, []);

  async function handleStart() {
    try {
      await recorder.prepareToRecordAsync();
      recorder.record();
      setIsActive(true);
      setStatusText('Listening...');
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e));
      setStatusText('Microphone error');
      onError?.(err);
    }
  }

  async function handleStop() {
    if (!isActive) return;
    try {
      await recorder.stop();
      setIsActive(false);
      setIsLoading(true);
      setStatusText('Chef Marco is thinking...');

      const uri = recorder.uri;
      if (!uri) throw new Error('No audio recorded');

      // Read the WAV file via expo-file-system v2 class API
      const recordingFile = new File(uri);
      const audioArrayBuffer = await recordingFile.arrayBuffer();
      // Strip RIFF header → raw PCM base64 for backend
      const { pcmBase64, sampleRate } = stripWavHeaderFromBuffer(audioArrayBuffer);

      const res = await voice({ audio_base64: pcmBase64, sample_rate: sampleRate });
      onTranscript?.('Voice response received');

      // Wrap backend PCM response in WAV container → write to cache → play
      const wavResponseBytes = buildWavBytes(res.audio_base64, res.sample_rate ?? 24000);
      const responseFile = new File(Paths.cache, 'chef_response_' + Date.now() + '.wav');
      const writer = responseFile.writableStream().getWriter();
      await writer.write(wavResponseBytes);
      await writer.close();

      try { tempFileRef.current?.delete(); } catch { /* ignore */ }
      tempFileRef.current = responseFile;

      player.replace({ uri: responseFile.uri });
      player.play();
      setIsPlaying(true);
      setStatusText('Chef Marco is speaking...');

      // Poll until playback ends (expo-audio Player)
      const checkDone = setInterval(() => {
        if (!player.playing) {
          clearInterval(checkDone);
          setIsPlaying(false);
          setStatusText('Tap to speak with Chef Marco');
        }
      }, 500);
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e));
      setIsLoading(false);
      setIsPlaying(false);
      setStatusText('Error — tap to try again');
      Alert.alert('Voice Error', err.message);
      onError?.(err);
    } finally {
      setIsLoading(false);
    }
  }

  // Pick FAB icon and variant for the current state
  const fabIcon = isLoading ? 'loading' : isActive ? 'stop' : isPlaying ? 'volume-high' : 'microphone';
  const fabVariant: 'primary' | 'secondary' | 'tertiary' | 'surface' = isActive
    ? 'tertiary'
    : isPlaying
    ? 'secondary'
    : 'primary';
  const { colors } = useTheme();

  return (
    <View style={{ alignItems: 'center', gap: 8, paddingVertical: 12 }}>
      <FAB
        icon={fabIcon}
        variant={fabVariant}
        loading={isLoading}
        onPress={isActive ? handleStop : handleStart}
        disabled={isLoading}
        label={statusText}
        size="medium"
      />
    </View>
  );
}
