/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Adres backendu przy wdrożeniu (np. https://wodoskop-api.onrender.com) – bez „/” na końcu.
   * Pusty / brak = względne `/api` (Docker i `npm run dev` z proxy Vite).
   */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
