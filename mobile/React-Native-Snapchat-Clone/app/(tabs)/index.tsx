import * as React from "react";
import { SafeAreaView, View } from "react-native";

import {
  BarcodeScanningResult,
  CameraMode,
  CameraView,
  FlashMode,
} from "expo-camera";
import BottomRowTools from "@/components/BottomRowTools";
import MainRowActions from "@/components/MainRowActions";
import PictureView from "@/components/PictureView";
import Animated, {
  FadeIn,
  FadeOut,
  LinearTransition,
} from "react-native-reanimated";
import CameraTools from "@/components/CameraTools";
import VideoViewComponent from "@/components/VideoView";
import BarcodeInsightView from "@/components/BarcodeInsightView";
import { Chip } from "react-native-paper";

export default function HomeScreen() {
  const cameraRef = React.useRef<CameraView>(null);
  const [cameraMode, setCameraMode] = React.useState<CameraMode>("picture");
  const [cameraTorch, setCameraTorch] = React.useState<boolean>(false);
  const [cameraFlash, setCameraFlash] = React.useState<FlashMode>("off");
  const [cameraFacing, setCameraFacing] = React.useState<"front" | "back">(
    "back"
  );
  const [cameraZoom, setCameraZoom] = React.useState<number>(0);
  const [picture, setPicture] = React.useState<string>(""); // "https://picsum.photos/seed/696/3000/2000"
  const [video, setVideo] = React.useState<string>("");

  const [isRecording, setIsRecording] = React.useState<boolean>(false);
  const [scannedBarcode, setScannedBarcode] = React.useState<{ data: string; type: string } | null>(null);
  const [activeBarcode, setActiveBarcode] = React.useState<{ data: string; type: string } | null>(null);
  const barcodeTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleBarcodeScanned = (result: BarcodeScanningResult) => {
    if (!result.data || activeBarcode) return;
    setScannedBarcode({ data: result.data, type: result.type });
    if (barcodeTimeoutRef.current) clearTimeout(barcodeTimeoutRef.current);
    barcodeTimeoutRef.current = setTimeout(() => setScannedBarcode(null), 4000);
  };

  async function handleTakePicture() {
    const response = await cameraRef.current?.takePictureAsync({});
    setPicture(response!.uri);
  }

  async function toggleRecord() {
    if (isRecording) {
      cameraRef.current?.stopRecording();
      setIsRecording(false);
    } else {
      setIsRecording(true);
      const response = await cameraRef.current?.recordAsync();
      setVideo(response!.uri);
    }
  }


  if (picture) return <PictureView picture={picture} setPicture={setPicture} />;
  if (video) return <VideoViewComponent video={video} setVideo={setVideo} />;
  if (activeBarcode) {
    return (
      <BarcodeInsightView
        barcode={activeBarcode}
        onClose={() => setActiveBarcode(null)}
      />
    );
  }
  return (
    <Animated.View
      layout={LinearTransition}
      entering={FadeIn.duration(1000)}
      exiting={FadeOut.duration(1000)}
      style={{ flex: 1 }}
    >
      <CameraView
        ref={cameraRef}
        style={{ flex: 1 }}
        facing={cameraFacing}
        mode={cameraMode}
        zoom={cameraZoom}
        enableTorch={cameraTorch}
        flash={cameraFlash}
        barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e", "code128", "code39", "qr"] }}
        onBarcodeScanned={handleBarcodeScanned}
        onCameraReady={() => {}}
      >
        <SafeAreaView style={{ flex: 1, paddingTop: 40 }}>
          <View style={{ flex: 1, padding: 6 }}>
            {scannedBarcode && (
              <Chip
                icon="barcode-scan"
                onPress={() => {
                  setActiveBarcode(scannedBarcode);
                  setScannedBarcode(null);
                }}
                style={{
                  position: "absolute",
                  alignSelf: "center",
                  top: "60%",
                  zIndex: 10,
                  backgroundColor: "rgba(0,0,0,0.75)",
                }}
                textStyle={{ color: "#fff" }}
              >
                Tap to analyze product
              </Chip>
            )}
            <CameraTools
              cameraZoom={cameraZoom}
              cameraFlash={cameraFlash}
              cameraTorch={cameraTorch}
              setCameraZoom={setCameraZoom}
              setCameraFacing={setCameraFacing}
              setCameraTorch={setCameraTorch}
              setCameraFlash={setCameraFlash}
            />
            <MainRowActions
              isRecording={isRecording}
              handleTakePicture={
                cameraMode === "picture" ? handleTakePicture : toggleRecord
              }
              cameraMode={cameraMode}
            />
            <BottomRowTools
              cameraMode={cameraMode}
              setCameraMode={setCameraMode}
            />
          </View>
        </SafeAreaView>
      </CameraView>
    </Animated.View>
  );
}
