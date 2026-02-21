import { useEffect } from 'react';
import { loadAndSetApiBaseUrl } from '@/api/init';

export function useSnapDishApiInit() {
  useEffect(() => {
    loadAndSetApiBaseUrl();
  }, []);
}
