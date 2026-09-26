import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
  test: {
    environment: 'jsdom',
    include: ['src/App.test.tsx', 'src/components/PilotExamples.test.tsx', 'src/components/AIInterpretation.test.tsx'],
    coverage: {
      provider: 'v8',
      include: ['src/components/PilotExamples.tsx', 'src/components/AIInterpretation.tsx'],
      reporter: ['text'],
    },
  },
})
