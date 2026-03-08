import * as React from "react";
import { StyleSheet, Platform, KeyboardAvoidingView, ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getApiBaseUrl, setApiBaseUrl } from "@/src/api/client";
import { Button, Text, TextInput } from "react-native-paper";

const API_URL_KEY = "snapdish_api_url";

export default function SettingsScreen() {
  const [apiUrl, setApiUrl] = React.useState(getApiBaseUrl());
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    AsyncStorage.getItem(API_URL_KEY).then((url) => {
      if (url) setApiUrl(url);
    });
  }, []);

  const save = async () => {
    const trimmed = apiUrl.trim();
    if (!trimmed) return;
    setApiBaseUrl(trimmed);
    await AsyncStorage.setItem(API_URL_KEY, trimmed);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={styles.scroll}>
          <Text variant="headlineMedium" style={styles.title}>Settings</Text>
          <Text variant="labelLarge" style={styles.label}>API Base URL</Text>
          <Text variant="bodySmall" style={styles.hint}>
            Set EXPO_PUBLIC_API_URL in EAS for builds, or enter your production API URL below.
          </Text>
          <TextInput
            value={apiUrl}
            onChangeText={setApiUrl}
            placeholder="https://api.snapdish.app"
            mode="outlined"
            autoCapitalize="none"
            autoCorrect={false}
            style={styles.input}
          />
          <Button
            mode="contained"
            onPress={save}
            icon={saved ? "check" : "content-save"}
            style={styles.button}
          >
            {saved ? "Saved!" : "Save URL"}
          </Button>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 20, paddingBottom: 40 },
  title: { marginBottom: 24 },
  label: { marginBottom: 4 },
  hint: { color: "#666", marginBottom: 12 },
  input: { marginBottom: 12 },
  button: { marginTop: 4 },
});
