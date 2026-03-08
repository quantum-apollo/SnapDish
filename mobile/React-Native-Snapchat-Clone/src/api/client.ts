/**
 * SnapDish API client. Production-only: no localhost fallback.
 * Base URL must be set via EAS (EXPO_PUBLIC_API_URL or extra.BACKEND_URL) or in-app Settings.
 *
 * Authentication: all requests include a Cognito Bearer token automatically.
 * Call setAuthTokenProvider() once in AuthContext to wire up the token getter.
 */

import Constants from 'expo-constants';

const API_URL_REQUIRED = 'API URL not configured. Set EXPO_PUBLIC_API_URL in EAS (or extra.BACKEND_URL in app.json) or configure in Settings.';

function getDefaultBaseUrl(): string {
  const fromExtra = Constants.expoConfig?.extra?.BACKEND_URL as string | undefined;
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  return (fromExtra ?? fromEnv ?? '').trim();
}

let apiBaseUrl = getDefaultBaseUrl();

export function setApiBaseUrl(url: string) {
  apiBaseUrl = (url ?? '').trim().replace(/\/$/, '');
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}

function requireApiBaseUrl(): string {
  const base = getApiBaseUrl();
  if (!base) {
    throw new Error(API_URL_REQUIRED);
  }
  return base;
}

// ---------------------------------------------------------------------------
// Auth token provider — set by AuthContext on mount
// ---------------------------------------------------------------------------

/** Function that returns a valid (possibly refreshed) Bearer token, or null. */
let _getToken: (() => Promise<string | null>) | null = null;

/**
 * Wire the auth token getter into the API client.
 * Called once from AuthContext after it initializes.
 */
export function setAuthTokenProvider(getter: () => Promise<string | null>) {
  _getToken = getter;
}

/** Build Authorization header value. Returns empty string if not authenticated. */
async function authHeader(): Promise<Record<string, string>> {
  if (!_getToken) return {};
  const token = await _getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/** In-memory cache for analyze responses (TTL 5 min). Enterprise: reduces duplicate calls. */
const CACHE_TTL_MS = 5 * 60 * 1000;
const analyzeCache = new Map<string, { response: AnalyzeResponse; ts: number }>();

function cacheKey(req: AnalyzeRequest): string {
  return JSON.stringify({ u: req.user_text ?? '', img: req.image_base64 ? 'present' : '', loc: req.location ?? null });
}

export interface AnalyzeRequest {
  user_text?: string | null;
  image_base64?: string | null;
  location?: { lat: number; lng: number } | null;
}

export interface AnalyzeResponse {
  cooking_guidance: string;
  detected_ingredients?: Array<{ name: string; confidence: string; notes?: string | null }>;
  nearby_stores?: Array<{ name: string; address?: string | null; distance_km?: number | null }>;
  grocery_list?: Array<{ item: string; quantity?: string | null; category?: string | null }>;
  nutrition?: Record<string, unknown>;
  safety_notes?: string[];
  [key: string]: unknown;
}

export async function analyze(body: AnalyzeRequest): Promise<AnalyzeResponse> {
  const key = cacheKey(body);
  const cached = analyzeCache.get(key);
  if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
    return cached.response;
  }
  const base = requireApiBaseUrl();
  const res = await fetch(`${base}/v1/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  const response = (await res.json()) as AnalyzeResponse;
  analyzeCache.set(key, { response, ts: Date.now() });
  return response;
}

export interface VoiceRequest {
  audio_base64: string;
  sample_rate?: number;
}

export interface VoiceResponse {
  audio_base64: string;
  sample_rate: number;
}

export async function voice(body: VoiceRequest): Promise<VoiceResponse> {
  const base = requireApiBaseUrl();
  const res = await fetch(`${base}/v1/voice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface MealAlternative {
  name: string;
  cuisine_tags: string[];
  dietary_tags: string[];
  calories_kcal?: number | null;
  why_safe: string;
  image_url?: string | null;
  source: string;
}

export async function getMealAlternatives(query: string, limit = 5): Promise<MealAlternative[]> {
  const base = requireApiBaseUrl();
  const params = new URLSearchParams({ query, limit: String(limit) });
  const res = await fetch(`${base}/v1/meal/alternatives?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getDietaryProfile(): Promise<Record<string, unknown>> {
  const base = requireApiBaseUrl();
  const res = await fetch(`${base}/v1/profile/dietary`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function updateDietaryProfile(profile: Record<string, unknown>): Promise<Record<string, unknown>> {
  const base = requireApiBaseUrl();
  const res = await fetch(`${base}/v1/profile/dietary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeader()) },
    body: JSON.stringify(profile),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}
