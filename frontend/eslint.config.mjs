import babelParser from '@babel/eslint-parser'
import pluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'

const babelOptions = {
  requireConfigFile: false,
  babelOptions: {
    plugins: ['@babel/plugin-syntax-typescript'],
  },
}

export default [
  {
    ignores: ['dist/**', 'src/generated/**', 'playwright-report/**', 'test-results/**'],
  },
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: babelParser,
      parserOptions: babelOptions,
    },
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: babelParser,
        ...babelOptions,
      },
    },
  },
]
