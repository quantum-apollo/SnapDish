import { useState } from "react";
import { Image } from "expo-image";
import { Alert, View, StyleSheet } from "react-native";
import { File } from "expo-file-system";
import IconButton from "./IconButton";
import { shareAsync } from "expo-sharing";
import { saveToLibraryAsync } from "expo-media-library";
import Animated, {
  FadeIn,
  FadeOut,
  LinearTransition,
} from "react-native-reanimated";
import { analyze } from "@/src/api/client";
import { Button } from "react-native-paper";

interface PictureViewProps {
  picture: string;
  setPicture: React.Dispatch<React.SetStateAction<string>>;
}

export default function PictureView({ picture, setPicture }: PictureViewProps) {
  const [analyzing, setAnalyzing] = useState(false);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const picFile = new File(picture);
      const picBuffer = await picFile.arrayBuffer();
      const picBytes = new Uint8Array(picBuffer);
      let bin = '';
      for (let i = 0; i < picBytes.length; i++) bin += String.fromCharCode(picBytes[i]);
      const base64 = btoa(bin);
      const res = await analyze({ image_base64: base64 });
      const guidance = res.cooking_guidance || "No guidance returned.";
      const preview = guidance.length > 400 ? guidance.slice(0, 397) + "…" : guidance;
      Alert.alert("Chef Marco", preview, [{ text: "OK" }]);
    } catch (e) {
      Alert.alert("Error", (e instanceof Error ? e.message : String(e)), [{ text: "OK" }]);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <Animated.View
      layout={LinearTransition}
      entering={FadeIn}
      exiting={FadeOut}
      style={{ flex: 1 }}
    >
      <View
        style={{
          position: "absolute",
          right: 6,
          zIndex: 1,
          paddingTop: 50,
          gap: 16,
        }}
      >
        <IconButton
          onPress={async () => {
            saveToLibraryAsync(picture);
            Alert.alert("✅ Picture saved!");
          }}
          iosName={"arrow.down"}
          androidName="close"
        />
        <IconButton
          onPress={() => setPicture("")}
          iosName={"square.dashed"}
          androidName="close"
        />
        <IconButton
          onPress={() => setPicture("")}
          iosName={"circle.dashed"}
          androidName="close"
        />
        <IconButton
          onPress={() => setPicture("")}
          iosName={"triangle"}
          androidName="close"
        />
        <IconButton
          onPress={async () => await shareAsync(picture)}
          iosName={"square.and.arrow.up"}
          androidName="close"
        />
      </View>

      <View
        style={{
          position: "absolute",
          zIndex: 1,
          paddingTop: 50,
          left: 6,
        }}
      >
        <IconButton
          onPress={() => setPicture("")}
          iosName={"xmark"}
          androidName="close"
        />
      </View>
      <Image
        source={picture}
        style={{
          height: "100%",
          width: "100%",
          borderRadius: 5,
        }}
      />
      <View style={localStyles.analyzeBar}>
        <Button
          mode="contained"
          onPress={handleAnalyze}
          disabled={analyzing}
          loading={analyzing}
          icon="chef-hat"
          contentStyle={{ paddingVertical: 6 }}
        >
          Analyze with Chef Marco
        </Button>
      </View>
    </Animated.View>
  );
}

const localStyles = StyleSheet.create({
  analyzeBar: {
    position: "absolute",
    bottom: 40,
    left: 20,
    right: 20,
    zIndex: 1,
    alignItems: "center",
  },
});
