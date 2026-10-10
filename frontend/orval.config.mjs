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
        mutator: {
          path: './src/shared/api/request.ts',
          name: 'aimaRequest',
        },
        formData: {
          arrayHandling: 'serialize',
        },
        fetch: {
          includeHttpResponseReturnType: false,
        },
      },
    },
  },
})
