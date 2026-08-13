import { defineConfig } from 'orval'

export default defineConfig({
  aima: {
    input: {
      target: '../contracts/openapi/openapi.json',
    },
    output: {
      mode: 'single',
      target: 'src/generated/api/client.ts',
      client: 'fetch',
      override: {
        fetch: {
          includeHttpResponseReturnType: false,
          forceSuccessResponse: true,
        },
      },
    },
  },
})
