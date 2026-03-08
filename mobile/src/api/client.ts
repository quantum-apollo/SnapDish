/**
 * SnapDish API client. Production-only: no localhost. Base URL from EAS (EXPO_PUBLIC_API_URL / extra.BACKEND_URL) or Settings.
 * Includes in-memory cache (5-minute TTL) for analyze responses.
 */

let apiBaseUrl = '';

export function setApiBaseUrl(url: string) {
  apiBaseUrl = (url ?? '').trim().replace(/\/$/, '');
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}

function requireBaseUrl(): string {
  if (!apiBaseUrl) {
    throw new Error('API URL not configured. Set EXPO_PUBLIC_API_URL in EAS or configure in Settings.');
  }
  return apiBaseUrl;
}

/** In-memory cache for analyze responses (TTL 5 min) */
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
  const base = requireBaseUrl();
  const res = await fetch(`${base}/v1/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  const base = requireBaseUrl();
  const res = await fetch(`${base}/v1/voice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  const base = requireBaseUrl();
  const params = new URLSearchParams({ query, limit: String(limit) });
  const res = await fetch(`${base}/v1/meal/alternatives?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

