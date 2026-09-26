import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/components/PilotExamples.test.tsx', 'src/components/AIInterpretation.test.tsx'],
    coverage: {
      provider: 'v8',
      include: ['src/components/PilotExamples.tsx', 'src/components/AIInterpretation.tsx'],
      reporter: ['text'],
    },
  },
})
