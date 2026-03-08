/**
 * SnapDish Login Screen
 * Opens the Cognito Hosted UI (PKCE OAuth 2.0) for sign-in.
 * Redirects to the main app automatically after successful authentication.
 */

import { useAuth } from '@/src/auth/AuthContext';
import { useRouter } from 'expo-router';
import React, { useEffect } from 'react';
import {
  ActivityIndicator,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function LoginScreen() {
  const { signIn, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // Redirect to main app once authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.replace('/(tabs)');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#FFD700" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        {/* Logo / brand */}
        <View style={styles.logoContainer}>
          <Text style={styles.logoText}>SnapDish</Text>
          <Text style={styles.tagline}>Your AI food companion</Text>
        </View>

        {/* Features list */}
        <View style={styles.features}>
          {[
            '📸  Analyze any dish from a photo',
            '🧑‍🍳  Personalized chef guidance',
            '🥗  Dietary-aware meal suggestions',
            '🔊  Real-time voice cooking assistant',
          ].map((line) => (
            <Text key={line} style={styles.featureText}>
              {line}
            </Text>
          ))}
        </View>

        {/* Sign in button */}
        <TouchableOpacity
          style={styles.signInButton}
          onPress={signIn}
          activeOpacity={0.85}
          accessibilityRole="button"
          accessibilityLabel="Sign in with your account"
        >
          <Text style={styles.signInButtonText}>Sign In</Text>
        </TouchableOpacity>

        <Text style={styles.disclaimer}>
          By signing in you agree to our Terms of Service and Privacy Policy.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0d0d',
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0d0d0d',
  },
  content: {
    flex: 1,
    paddingHorizontal: 32,
    paddingTop: 60,
    paddingBottom: 40,
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 40,
  },
  logoText: {
    fontSize: 48,
    fontWeight: '800',
    color: '#FFD700',
    letterSpacing: -1,
  },
  tagline: {
    fontSize: 16,
    color: '#aaa',
    marginTop: 8,
  },
  features: {
    width: '100%',
    gap: 16,
    marginBottom: 48,
  },
  featureText: {
    fontSize: 16,
    color: '#e0e0e0',
    lineHeight: 24,
  },
  signInButton: {
    width: '100%',
    backgroundColor: '#FFD700',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 20,
    shadowColor: '#FFD700',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 6,
  },
  signInButtonText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#0d0d0d',
  },
  disclaimer: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
    lineHeight: 18,
  },
});
