import { createTamaguiConfig } from '@tamagui/core';

const config = createTamaguiConfig({
  theme: {
    color: {
      background: '#fff',
      foreground: '#222',
      accent: '#FF6B6B',
    },
    spacing: {
      small: 8,
      medium: 16,
      large: 24,
    },
    borderRadius: {
      small: 8,
      medium: 16,
      large: 28,
    },
  },
  fonts: {
    heading: 'System',
    body: 'System',
  },
});

export default config;
