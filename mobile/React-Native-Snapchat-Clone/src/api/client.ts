/**
 * SnapDish API client. Base URL is set in Settings and stored in AsyncStorage.
 */

let apiBaseUrl = 'http://localhost:8000';

export function setApiBaseUrl(url: string) {
  apiBaseUrl = url.replace(/\/$/, '');
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
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
  const res = await fetch(`${apiBaseUrl}/v1/analyze`, {
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

export interface VoiceRequest {
  audio_base64: string;
  sample_rate?: number;
}

export interface VoiceResponse {
  audio_base64: string;
  sample_rate: number;
}

export async function voice(body: VoiceRequest): Promise<VoiceResponse> {
  const res = await fetch(`${apiBaseUrl}/v1/voice`, {
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
