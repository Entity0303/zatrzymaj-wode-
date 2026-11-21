import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './theme/index.css'
import App from './App.tsx'
import { TooltipProvider } from '@/components/ui/tooltip'
import { LanguageProvider } from '@/components/LanguageProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LanguageProvider>
      <TooltipProvider delayDuration={300}>
        <App />
      </TooltipProvider>
    </LanguageProvider>
  </StrictMode>,
)
