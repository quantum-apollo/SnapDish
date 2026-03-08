import * as React from "react";
import { View, ScrollView, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  ActivityIndicator,
  Button,
  Card,
  Chip,
  Text,
} from "react-native-paper";
import Animated, { FadeIn, FadeOut, LinearTransition } from "react-native-reanimated";
import IconButton from "./IconButton";
import { analyze, AnalyzeResponse } from "@/src/api/client";

interface BarcodeInsightViewProps {
  barcode: { data: string; type: string };
  onClose: () => void;
}

export default function BarcodeInsightView({ barcode, onClose }: BarcodeInsightViewProps) {
  const [loading, setLoading] = React.useState(true);
  const [result, setResult] = React.useState<AnalyzeResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    analyze({
      user_text: `Food product barcode scanned — type: ${barcode.type}, value: ${barcode.data}. Identify this product if possible and provide: product name, key ingredients, nutritional highlights, allergens, health considerations, and any cooking or serving suggestions from Chef Marco.`,
    })
      .then(setResult)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [barcode.data, barcode.type]);

  return (
    <Animated.View
      layout={LinearTransition}
      entering={FadeIn}
      exiting={FadeOut}
      style={{ flex: 1 }}
    >
      <SafeAreaView style={styles.safe}>
        {/* Header */}
        <View style={styles.header}>
          <IconButton iosName="xmark" androidName="close" onPress={onClose} />
          <Text variant="titleMedium" style={styles.headerTitle}>Product Insights</Text>
          <View style={{ width: 44 }} />
        </View>

        <ScrollView contentContainerStyle={styles.scroll}>
          {/* Barcode identity card */}
          <Card style={styles.barcodeCard}>
            <Card.Content>
              <Text variant="labelSmall" style={styles.barcodeLabel}>SCANNED BARCODE</Text>
              <Text variant="bodyLarge" style={styles.barcodeData}>{barcode.data}</Text>
              <Text variant="bodySmall" style={styles.barcodeType}>{barcode.type}</Text>
            </Card.Content>
          </Card>

          {loading && (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" />
              <Text variant="bodyMedium" style={styles.loadingText}>
                Chef Marco is looking up this product…
              </Text>
            </View>
          )}

          {error && (
            <Card style={styles.errorCard}>
              <Card.Content>
                <Text variant="bodyMedium" style={{ color: "#c00" }}>{error}</Text>
              </Card.Content>
              <Card.Actions>
                <Button onPress={onClose}>Close</Button>
              </Card.Actions>
            </Card>
          )}

          {result && (
            <>
              {/* Chef Marco's analysis */}
              <Card style={styles.card}>
                <Card.Title title="Chef Marco's Analysis" />
                <Card.Content>
                  <Text variant="bodyMedium">{result.cooking_guidance}</Text>
                </Card.Content>
              </Card>

              {/* Detected ingredients */}
              {result.detected_ingredients && result.detected_ingredients.length > 0 && (
                <Card style={styles.card}>
                  <Card.Title title="Ingredients" />
                  <Card.Content style={styles.chipsWrap}>
                    {result.detected_ingredients.map((ing, i) => (
                      <Chip key={i} compact style={styles.chip}>
                        {ing.name}
                      </Chip>
                    ))}
                  </Card.Content>
                </Card>
              )}

              {/* Safety & allergens */}
              {result.safety_notes && result.safety_notes.length > 0 && (
                <Card style={[styles.card, styles.safetyCard]}>
                  <Card.Title title="Safety & Allergens" />
                  <Card.Content>
                    {result.safety_notes.map((note, i) => (
                      <Text key={i} variant="bodySmall" style={styles.bulletRow}>
                        • {note}
                      </Text>
                    ))}
                  </Card.Content>
                </Card>
              )}

              {/* Grocery / pairing suggestions */}
              {result.grocery_list && result.grocery_list.length > 0 && (
                <Card style={styles.card}>
                  <Card.Title title="Pairs Well With" />
                  <Card.Content>
                    {result.grocery_list.map((item, i) => (
                      <Text key={i} variant="bodySmall" style={styles.bulletRow}>
                        • {item.item}
                        {item.quantity ? ` — ${item.quantity}` : ""}
                      </Text>
                    ))}
                  </Card.Content>
                </Card>
              )}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#fff" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#f0f0f0",
  },
  headerTitle: { fontWeight: "600" },
  scroll: { padding: 16, paddingBottom: 40 },
  barcodeCard: { backgroundColor: "#f8f8f8", marginBottom: 12 },
  barcodeLabel: { color: "#999", letterSpacing: 0.8, marginBottom: 4 },
  barcodeData: { fontFamily: "monospace", fontWeight: "600" },
  barcodeType: { color: "#888", marginTop: 2 },
  loadingContainer: { alignItems: "center", paddingVertical: 48 },
  loadingText: { color: "#666", marginTop: 16, textAlign: "center" },
  errorCard: { backgroundColor: "#fff0f0", marginBottom: 12 },
  card: { marginBottom: 12 },
  safetyCard: { backgroundColor: "#fffbf0" },
  chipsWrap: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: { marginBottom: 4 },
  bulletRow: { marginBottom: 4, lineHeight: 20 },
});
