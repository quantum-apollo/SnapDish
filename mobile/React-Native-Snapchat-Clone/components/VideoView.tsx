import { useEffect, useRef, useState } from "react";
import { useVideoPlayer, VideoView } from "expo-video";
import { Alert, View } from "react-native";
import IconButton from "./IconButton";
import { IconButton as PaperIconButton } from "react-native-paper";
import { shareAsync } from "expo-sharing";
import { createAssetAsync, getAssetInfoAsync, saveToLibraryAsync } from "expo-media-library";
import { File } from "expo-file-system";
import Animated, {
  FadeIn,
  FadeOut,
  LinearTransition,
} from "react-native-reanimated";
import { analyze } from "@/src/api/client";

interface VideoViewProps {
  video: string;
  setVideo: React.Dispatch<React.SetStateAction<string>>;
}
export default function VideoViewComponent({
  video,
  setVideo,
}: VideoViewProps) {
  const ref = useRef<VideoView>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const player = useVideoPlayer(video, (player) => {
    player.loop = true;
    player.muted = true;
    player.play();
  });

  /**
   * Save video to library → get its thumbnail URI → send to /v1/analyze.
   * This gives Chef Marco a visual frame from the video for multimodal analysis.
   */
  const handleAnalyzeVideo = async () => {
    setAnalyzing(true);
    player.pause();
    try {
      const asset = await createAssetAsync(video);
      const info = await getAssetInfoAsync(asset);
      const thumbnailUri = info.localUri ?? info.uri;
      const thumbFile = new File(thumbnailUri);
      const thumbBuffer = await thumbFile.arrayBuffer();
      const bytes = new Uint8Array(thumbBuffer);
      let binary = '';
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      const base64 = btoa(binary);
      const res = await analyze({ image_base64: base64 });
      const guidance = res.cooking_guidance || "No guidance returned.";
      const preview = guidance.length > 400 ? guidance.slice(0, 397) + "…" : guidance;
      Alert.alert("Chef Marco (Video Frame)", preview, [{ text: "OK" }]);
    } catch (e) {
      Alert.alert("Error", e instanceof Error ? e.message : String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    const subscription = player.addListener("playingChange", (isPlaying) => {
      setIsPlaying(isPlaying);
    });

    return () => {
      subscription.remove();
    };
  }, [player]);

  return (
    <Animated.View
      layout={LinearTransition}
      entering={FadeIn}
      exiting={FadeOut}
    >
      <View
        style={{
          position: "absolute",
          right: 6,
          zIndex: 1,
          paddingTop: 100,
          gap: 16,
        }}
      >
        <IconButton
          onPress={() => setVideo("")}
          iosName={"xmark"}
          androidName="close"
        />
        <IconButton
          onPress={async () => {
            saveToLibraryAsync(video);
            Alert.alert("✅ video saved!");
          }}
          iosName={"arrow.down"}
          androidName="close"
        />
        <IconButton
          onPress={async () => await shareAsync(video)}
          iosName={"square.and.arrow.up"}
          androidName="close"
        />
        {/* react-native-paper Material Design 3 — AI analyze action */}
        <PaperIconButton
          icon={analyzing ? 'loading' : 'brain'}
          mode="contained"
          disabled={analyzing}
          onPress={handleAnalyzeVideo}
          size={20}
          style={{ backgroundColor: '#00000080', margin: 0 }}
          iconColor="white"
        />
        <IconButton
          iosName={isPlaying ? "pause" : "play"}
          androidName={isPlaying ? "pause" : "play"}
          onPress={() => {
            if (isPlaying) {
              player.pause();
            } else {
              player.play();
            }
            setIsPlaying(!isPlaying);
          }}
        />
      </View>
      <VideoView
        ref={ref}
        style={{
          width: "100%",
          height: "100%",
        }}
        player={player}
        allowsFullscreen
        nativeControls={true}
      />
    </Animated.View>
  );
}
