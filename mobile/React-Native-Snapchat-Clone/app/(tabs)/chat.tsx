import * as React from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { analyze, getMealAlternatives } from '../../src/api/client';
import VoiceStreamer from '../../components/VoiceStreamer';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button, Text, TextInput, IconButton, Chip, ActivityIndicator } from 'react-native-paper';

interface MealAlt {
  name: string;
  why_safe: string;
  calories_kcal?: number | null;
}

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
  alternatives?: MealAlt[];
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
  React.useEffect(() => {
    scrollViewRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  async function sendMessage() {
    if (!input.trim()) return;
    const userText = input.trim();
    const userMsg: Message = {
      id: Date.now().toString(),
      text: userText,
      isUser: true,
      timestamp: new Date(),
    };
    setMessages((msgs) => [...msgs, userMsg]);
    setInput('');
    setLoading(true);

    try {
      // Run analyze + meal alternatives in parallel for richer response
      const [res, alts] = await Promise.allSettled([
        analyze({ user_text: userText }),
        getMealAlternatives(userText, 4),
      ]);

      const guidance = res.status === 'fulfilled' ? (res.value.cooking_guidance || 'No response.') : 'Error getting response.';
      const alternatives = alts.status === 'fulfilled' ? alts.value.slice(0, 4).map((a) => ({ name: a.name, why_safe: a.why_safe, calories_kcal: a.calories_kcal })) : [];

      setMessages((msgs) => [
        ...msgs,
        {
          id: Date.now().toString() + '-ai',
          text: guidance,
          isUser: false,
          timestamp: new Date(),
          alternatives: alternatives.length > 0 ? alternatives : undefined,
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
      <View style={{ flex: 1, backgroundColor: '#fff' }}>
        {/* Voice assistant */}
        <VoiceStreamer />

        <ScrollView ref={scrollViewRef} style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
          {messages.map((msg) => (
            <View key={msg.id} style={{ alignSelf: msg.isUser ? 'flex-end' : 'flex-start', marginBottom: 12, maxWidth: '85%' }}>
              <View style={[styles.bubble, msg.isUser ? styles.bubbleUser : styles.bubbleAI]}>
                <Text style={[styles.bubbleText, { color: msg.isUser ? '#fff' : '#222' }]}>{msg.text}</Text>
              </View>
              {/* Meal alternatives chips */}
              {!msg.isUser && msg.alternatives && msg.alternatives.length > 0 && (
                <View style={styles.altsContainer}>
                  <Text variant="labelSmall" style={{ textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>Meal Alternatives</Text>
                  {msg.alternatives.map((alt, i) => (
                    <Chip key={i} style={{ marginBottom: 4 }} compact>
                      {alt.name}{alt.calories_kcal ? ` · ${Math.round(alt.calories_kcal)} kcal` : ''}
                    </Chip>
                  ))}
                </View>
              )}
            </View>
          ))}
          {loading && (
            <View style={{ alignSelf: 'flex-start', marginBottom: 12 }}>
              <ActivityIndicator color="#FF6B6B" />
            </View>
          )}
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Type your message..."
            mode="outlined"
            style={{ flex: 1 }}
            disabled={loading}
            onSubmitEditing={sendMessage}
            returnKeyType="send"
            right={<TextInput.Icon icon="send" onPress={sendMessage} disabled={loading} />}
          />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  bubble: { borderRadius: 16, padding: 12 },
  bubbleUser: { backgroundColor: '#FF6B6B' },
  bubbleAI: { backgroundColor: '#f8f8f8' },
  bubbleText: { fontSize: 16 },
  altsContainer: { marginTop: 8, gap: 6 },
  inputRow: { padding: 12, borderTopWidth: 1, borderTopColor: '#f0f0f0' },
});
