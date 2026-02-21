import AsyncStorage from '@react-native-async-storage/async-storage';
import { setApiBaseUrl } from '@/api/client';

const API_URL_KEY = 'snapdish_api_url';

export async function loadAndSetApiBaseUrl() {
  const url = await AsyncStorage.getItem(API_URL_KEY);
  if (url) setApiBaseUrl(url);
}
