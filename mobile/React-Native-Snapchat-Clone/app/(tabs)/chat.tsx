import * as React from 'react';
import { View, TextInput, TouchableOpacity, ScrollView, StyleSheet, Text } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { analyze } from '../../src/api/client';
import VoiceStreamer from '../../components/VoiceStreamer';
import { SafeAreaView } from 'react-native-safe-area-context';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
}

export default function ChatScreen() {
  const [input, setInput] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [messages, setMessages] = React.useState<Message[]>([
    {
      id: '1',
      text: "Ciao! I'm Chef Marco. Send me a photo of your dish or ask me anything about cooking!",
      isUser: false,
      timestamp: new Date(),
    },
  ]);
  const scrollViewRef = React.useRef<ScrollView>(null);

  // Real-time transcript state
  const [voiceTranscript, setVoiceTranscript] = React.useState<string>('');
  const [voiceError, setVoiceError] = React.useState<string | null>(null);

  React.useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  async function sendMessage() {
    if (!input.trim()) return;
    const userMsg: Message = {
      id: Date.now().toString(),
      text: input,
      isUser: true,
      timestamp: new Date(),
    };
    setMessages((msgs) => [...msgs, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const res = await analyze({ user_text: userMsg.text });
      setMessages((msgs) => [
        ...msgs,
        {
          id: Date.now().toString() + '-ai',
          text: res.cooking_guidance || 'No response.',
          isUser: false,
          timestamp: new Date(),
        },
      ]);
    } catch (e) {
      setMessages((msgs) => [
        ...msgs,
        {
          id: Date.now().toString() + '-err',
          text: 'Error: ' + (e instanceof Error ? e.message : 'Unknown error'),
          isUser: false,
          timestamp: new Date(),
        },
      ]);
    }
    setLoading(false);
  }

  return (
    <SafeAreaView style={{ flex: 1 }}>
      <View style={{ flex: 1, backgroundColor: '#fff', padding: 16 }}>
        {/* VoiceStreamer for real-time audio/voice */}
        <VoiceStreamer
          onTranscript={(text) => {
            setVoiceTranscript(text);
            // Optionally, add transcript as message when finalized
          }}
          onError={(err) => setVoiceError(err.message)}
        />
        {voiceTranscript ? (
          <View style={{ marginBottom: 8 }}>
            <Text style={{ color: '#222', fontStyle: 'italic' }}>Voice: {voiceTranscript}</Text>
          </View>
        ) : null}
        {voiceError ? (
          <View style={{ marginBottom: 8 }}>
            <Text style={{ color: 'red' }}>Voice error: {voiceError}</Text>
          </View>
        ) : null}
        <ScrollView ref={scrollViewRef} style={{ flex: 1 }}>
          {messages.map((msg) => (
            <View key={msg.id} style={{ alignSelf: msg.isUser ? 'flex-end' : 'flex-start', marginBottom: 12, maxWidth: '80%' }}>
              <View style={{ borderRadius: 16, backgroundColor: msg.isUser ? '#FF6B6B' : '#f8f8f8', padding: 12 }}>
                <Text style={{ color: msg.isUser ? '#fff' : '#222', fontSize: 16 }}>{msg.text}</Text>
              </View>
            </View>
          ))}
        </ScrollView>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 8 }}>
          <View style={{ flex: 1 }}>
            <TextInput
              value={input}
              onChangeText={setInput}
              placeholder="Type your message..."
              style={{ backgroundColor: '#f8f8f8', borderRadius: 16, padding: 12, fontSize: 16 }}
              editable={!loading}
              onSubmitEditing={sendMessage}
              returnKeyType="send"
            />
          </View>
          <View style={{ marginLeft: 8 }}>
            <TouchableOpacity onPress={sendMessage} disabled={loading}>
              <MaterialCommunityIcons name="send" size={28} color={loading ? '#ccc' : '#FF6B6B'} />
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({});
