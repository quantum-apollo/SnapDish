import { useEffect } from 'react';
import { loadAndSetApiBaseUrl } from '@/src/api/init';

export function useSnapDishApiInit() {
  useEffect(() => {
    loadAndSetApiBaseUrl();
  }, []);
}
