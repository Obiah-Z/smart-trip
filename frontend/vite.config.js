import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_API_BASE || 'http://127.0.0.1:8001'
  const allowedHosts = (env.VITE_ALLOWED_HOSTS || 'obiah.xyz,www.obiah.xyz,trip.obiah.xyz,8.153.15.37')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  return {
    plugins: [vue()],
    server: {
      port: 5174,
      allowedHosts,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/media': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
