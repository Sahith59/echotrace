import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.tsx'],
    coverage: {
      provider: 'v8',
      include: ['src/components/PilotExamples.tsx', 'src/components/AIInterpretation.tsx', 'src/components/CaseReview.tsx', 'src/components/DetectorComparison.tsx'],
      reporter: ['text'],
    },
  },
})
