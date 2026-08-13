import { defineConfig } from 'orval'

export default defineConfig({
  aima: {
    input: {
      target: '../contracts/openapi/openapi.json',
    },
    output: {
      mode: 'single',
      target: 'src/generated/api/client.ts',
      schemas: 'src/generated/api/models',
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
