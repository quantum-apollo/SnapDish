import {
  DarkTheme,
  DefaultTheme,
  ThemeProvider,
} from "@react-navigation/native";
import { useFonts } from "expo-font";
import { Stack, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { useSnapDishApiInit } from "@/src/api/useSnapDishApiInit";
import "react-native-reanimated";
import { PaperProvider, MD3LightTheme, MD3DarkTheme } from "react-native-paper";

import { useColorScheme } from "@/hooks/useColorScheme";
import { LogBox } from "react-native";
import { AuthProvider, useAuth } from "@/src/auth/AuthContext";

// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync();
LogBox.ignoreAllLogs(); //🥲

/** Route guard: redirects unauthenticated users to /login. */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return; // Wait for token restore
    const inAuthGroup = segments[0] === "login";
    if (!isAuthenticated && !inAuthGroup) {
      router.replace("/login");
    } else if (isAuthenticated && inAuthGroup) {
      router.replace("/(tabs)");
    }
  }, [isAuthenticated, isLoading, segments, router]);

  return <>{children}</>;
}

function RootLayoutInner() {
  useSnapDishApiInit();
  const colorScheme = useColorScheme();
  const [loaded] = useFonts({
    SpaceMono: require("../assets/fonts/SpaceMono-Regular.ttf"),
  });

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  if (!loaded) {
    return null;
  }

  return (
    <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>
      <PaperProvider theme={colorScheme === "dark" ? MD3DarkTheme : MD3LightTheme}>
        <AuthGuard>
          <Stack>
            <Stack.Screen name="login" options={{ headerShown: false }} />
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="+not-found" />
            <Stack.Screen
              name="media-library"
              options={{ presentation: "modal" }}
            />
            <Stack.Screen
              name="onboarding"
              options={{
                presentation: "fullScreenModal",
                headerShown: false,
                animation: "fade",
              }}
            />
          </Stack>
        </AuthGuard>
      </PaperProvider>
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutInner />
    </AuthProvider>
  );
}
