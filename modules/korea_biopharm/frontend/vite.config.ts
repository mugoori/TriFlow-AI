import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // 빌드 설정
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // 빌드 시 소스맵 생성 (디버깅용, 프로덕션에서는 false)
    sourcemap: false,
    // 청크 크기 경고 임계값
    chunkSizeWarningLimit: 1000,
  },
  // 개발 서버 설정
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  // 배포 시 base 경로 (같은 서버에서 서빙하므로 상대 경로)
  base: './',
})
