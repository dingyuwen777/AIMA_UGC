import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: '../contracts/openapi/openapi.json',
  output: 'src/generated/api',
  plugins: ['@hey-api/sdk'],
})
