

/** Znak marki: kropla w liściu (SPEC 4.1). Własny rysunek. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <rect width="40" height="40" rx="12" fill="#2E5B3F" />
      {/* liść */}
      <path d="M10 29c0-11 8-18 20-19-1 12-8 20-19 20" fill="#9DB896" />
      <path d="M11 29c5-6 10-10 16-15" stroke="#1F4230" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      {/* kropla */}
      <path d="M21 15.5c2.4 3 3.8 5.2 3.8 7a3.8 3.8 0 0 1-7.6 0c0-1.8 1.4-4 3.8-7z" fill="#E3F0FB" stroke="#2F80C9" strokeWidth="1.2" />
    </svg>
  )
}
