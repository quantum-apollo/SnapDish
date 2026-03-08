/**
 * SnapDish Auth Context — AWS Cognito, Authorization Code + PKCE
 *
 * Configure via app.json extra (or EAS env):
 *   extra.COGNITO_DOMAIN      — e.g. "your-pool.auth.us-east-1.amazoncognito.com"
 *   extra.COGNITO_CLIENT_ID   — Cognito App Client ID (no client secret for PKCE)
 *   extra.COGNITO_REGION      — e.g. "us-east-1"
 *   extra.COGNITO_USER_POOL_ID — e.g. "us-east-1_AbCdEfGhI"
 *
 * Tokens stored in expo-secure-store (iOS Keychain / Android Keystore).
 * Access token is automatically refreshed when expired (using refresh token).
 */

import * as AuthSession from 'expo-auth-session';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { setAuthTokenProvider } from '@/src/api/client';

WebBrowser.maybeCompleteAuthSession();

// ---------------------------------------------------------------------------
// Config (from app.json extra / EAS env)
// ---------------------------------------------------------------------------

function getCognitoConfig() {
  const extra = Constants.expoConfig?.extra ?? {};
  return {
    domain: (extra.COGNITO_DOMAIN as string | undefined) ?? process.env.EXPO_PUBLIC_COGNITO_DOMAIN ?? '',
    clientId: (extra.COGNITO_CLIENT_ID as string | undefined) ?? process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID ?? '',
    region: (extra.COGNITO_REGION as string | undefined) ?? process.env.EXPO_PUBLIC_COGNITO_REGION ?? '',
    userPoolId: (extra.COGNITO_USER_POOL_ID as string | undefined) ?? process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID ?? '',
  };
}

// ---------------------------------------------------------------------------
// Secure storage keys
// ---------------------------------------------------------------------------

const STORAGE_ACCESS_TOKEN = 'snapdish_access_token';
const STORAGE_REFRESH_TOKEN = 'snapdish_refresh_token';
const STORAGE_ID_TOKEN = 'snapdish_id_token';
const STORAGE_EXPIRES_AT = 'snapdish_expires_at';

async function saveTokens(tokens: {
  accessToken: string;
  refreshToken?: string;
  idToken?: string;
  expiresIn?: number;
}) {
  await SecureStore.setItemAsync(STORAGE_ACCESS_TOKEN, tokens.accessToken);
  if (tokens.refreshToken) {
    await SecureStore.setItemAsync(STORAGE_REFRESH_TOKEN, tokens.refreshToken);
  }
  if (tokens.idToken) {
    await SecureStore.setItemAsync(STORAGE_ID_TOKEN, tokens.idToken);
  }
  const expiresAt = Date.now() + (tokens.expiresIn ?? 3600) * 1000;
  await SecureStore.setItemAsync(STORAGE_EXPIRES_AT, String(expiresAt));
}

async function clearTokens() {
  await SecureStore.deleteItemAsync(STORAGE_ACCESS_TOKEN);
  await SecureStore.deleteItemAsync(STORAGE_REFRESH_TOKEN);
  await SecureStore.deleteItemAsync(STORAGE_ID_TOKEN);
  await SecureStore.deleteItemAsync(STORAGE_EXPIRES_AT);
}

async function loadStoredTokens(): Promise<{ accessToken: string | null; expiresAt: number; refreshToken: string | null }> {
  const [accessToken, expiresAtStr, refreshToken] = await Promise.all([
    SecureStore.getItemAsync(STORAGE_ACCESS_TOKEN),
    SecureStore.getItemAsync(STORAGE_EXPIRES_AT),
    SecureStore.getItemAsync(STORAGE_REFRESH_TOKEN),
  ]);
  return {
    accessToken,
    expiresAt: expiresAtStr ? parseInt(expiresAtStr, 10) : 0,
    refreshToken,
  };
}

// ---------------------------------------------------------------------------
// Token refresh via Cognito token endpoint
// ---------------------------------------------------------------------------

async function refreshAccessToken(refreshToken: string, clientId: string, domain: string): Promise<string | null> {
  const tokenEndpoint = `https://${domain}/oauth2/token`;
  try {
    const body = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: clientId,
      refresh_token: refreshToken,
    });
    const res = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
    if (!res.ok) return null;
    const data = await res.json();
    await saveTokens({
      accessToken: data.access_token,
      idToken: data.id_token,
      expiresIn: data.expires_in,
      // Cognito doesn't return a new refresh token on refresh — reuse existing
    });
    return data.access_token as string;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface AuthState {
  /** Bearer token to attach to API requests. Null = not authenticated. */
  accessToken: string | null;
  /** True while the initial token check or sign-in is in progress. */
  isLoading: boolean;
  /** True if the user is authenticated. */
  isAuthenticated: boolean;
  /** Open the Cognito Hosted UI login page (PKCE). */
  signIn: () => Promise<void>;
  /** Sign out: clear local tokens + open Cognito logout endpoint. */
  signOut: () => Promise<void>;
  /** Get a valid (possibly refreshed) access token. Returns null if signed out. */
  getValidToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthState>({
  accessToken: null,
  isLoading: true,
  isAuthenticated: false,
  signIn: async () => {},
  signOut: async () => {},
  getValidToken: async () => null,
});

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);

  const config = useMemo(() => getCognitoConfig(), []);
  const redirectUri = AuthSession.makeRedirectUri({ scheme: 'myapp', path: 'callback' });

  const discovery = useMemo<AuthSession.DiscoveryDocument | null>(() => {
    if (!config.domain) return null;
    const base = `https://${config.domain}`;
    return {
      authorizationEndpoint: `${base}/oauth2/authorize`,
      tokenEndpoint: `${base}/oauth2/token`,
      revocationEndpoint: `${base}/oauth2/revoke`,
      endSessionEndpoint: `${base}/logout`,
    };
  }, [config.domain]);

  const [authRequest, authResult, promptAsync] = AuthSession.useAuthRequest(
    {
      clientId: config.clientId,
      scopes: ['openid', 'email', 'profile'],
      redirectUri,
      responseType: AuthSession.ResponseType.Code,
      usePKCE: true,
    },
    discovery,
  );

  // On mount: restore tokens from secure storage
  useEffect(() => {
    (async () => {
      try {
        const stored = await loadStoredTokens();
        if (stored.accessToken) {
          // Check if still valid (with 60s buffer)
          if (stored.expiresAt > Date.now() + 60_000) {
            setAccessToken(stored.accessToken);
            setExpiresAt(stored.expiresAt);
          } else if (stored.refreshToken && config.domain && config.clientId) {
            // Try silent refresh
            const newToken = await refreshAccessToken(stored.refreshToken, config.clientId, config.domain);
            if (newToken) {
              setAccessToken(newToken);
              const newStored = await loadStoredTokens();
              setExpiresAt(newStored.expiresAt);
            } else {
              await clearTokens();
            }
          } else {
            await clearTokens();
          }
        }
      } finally {
        setIsLoading(false);
      }
    })();
  }, [config.clientId, config.domain]);

  // Handle auth code exchange after redirect
  useEffect(() => {
    if (!authResult || authResult.type !== 'success' || !discovery || !authRequest) return;

    (async () => {
      setIsLoading(true);
      try {
        const tokenResp = await AuthSession.exchangeCodeAsync(
          {
            clientId: config.clientId,
            code: authResult.params.code,
            redirectUri,
            extraParams: authRequest.codeVerifier
              ? { code_verifier: authRequest.codeVerifier }
              : {},
          },
          discovery,
        );
        await saveTokens({
          accessToken: tokenResp.accessToken,
          refreshToken: tokenResp.refreshToken ?? undefined,
          idToken: tokenResp.idToken ?? undefined,
          expiresIn: tokenResp.expiresIn ?? 3600,
        });
        setAccessToken(tokenResp.accessToken);
        setExpiresAt(Date.now() + (tokenResp.expiresIn ?? 3600) * 1000);
      } finally {
        setIsLoading(false);
      }
    })();
  }, [authResult]); // eslint-disable-line react-hooks/exhaustive-deps

  const getValidToken = useCallback(async (): Promise<string | null> => {
    if (!accessToken) return null;
    // Token still valid with 60s buffer
    if (expiresAt > Date.now() + 60_000) return accessToken;
    // Attempt silent refresh
    const stored = await loadStoredTokens();
    if (!stored.refreshToken || !config.domain || !config.clientId) {
      await clearTokens();
      setAccessToken(null);
      return null;
    }
    const newToken = await refreshAccessToken(stored.refreshToken, config.clientId, config.domain);
    if (newToken) {
      setAccessToken(newToken);
      const newStored = await loadStoredTokens();
      setExpiresAt(newStored.expiresAt);
      return newToken;
    }
    await clearTokens();
    setAccessToken(null);
    return null;
  }, [accessToken, expiresAt, config.clientId, config.domain]);

  const signIn = useCallback(async () => {
    if (!discovery || !authRequest) return;
    await promptAsync();
  }, [discovery, authRequest, promptAsync]);

  const signOut = useCallback(async () => {
    await clearTokens();
    setAccessToken(null);
    setExpiresAt(0);
    // Optionally open Cognito logout endpoint to clear the hosted UI session
    if (config.domain && config.clientId) {
      const logoutUrl = `https://${config.domain}/logout?client_id=${encodeURIComponent(config.clientId)}&logout_uri=${encodeURIComponent(redirectUri)}`;
      await WebBrowser.openBrowserAsync(logoutUrl);
    }
  }, [config.clientId, config.domain, redirectUri]);

  const value = useMemo<AuthState>(
    () => ({
      accessToken,
      isLoading,
      isAuthenticated: !!accessToken,
      signIn,
      signOut,
      getValidToken,
    }),
    [accessToken, isLoading, signIn, signOut, getValidToken],
  );

  // Wire token getter into API client whenever getValidToken changes
  useEffect(() => {
    setAuthTokenProvider(getValidToken);
  }, [getValidToken]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
