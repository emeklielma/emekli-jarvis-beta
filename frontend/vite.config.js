import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

const backend = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Telefon modu (npm run dev:phone): HTTPS ile 5174'te açılır. Telefon tarayıcısı
  // mikrofona sadece HTTPS sayfalarda izin verdiği için gerekli.
  const phoneMode = mode === 'phone'
  return {
    plugins: [react(), ...(phoneMode ? [basicSsl()] : [])],
    server: {
      // Aynı Wi-Fi'daki telefonun erişebilmesi için tüm ağ arayüzlerinden dinle
      host: true,
      port: phoneMode ? 5174 : 5173,
      strictPort: true,
      // WebSocket ve API isteklerini Python sunucusuna ilet; böylece telefon
      // "localhost:8000" yerine sayfanın açıldığı adres üzerinden bağlanır.
      proxy: {
        '/ws': { target: backend, ws: true, changeOrigin: true },
        '/api': { target: backend, changeOrigin: true },
      },
    },
  }
})
