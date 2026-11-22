/**
 * F32: „otwórz paszport w tej sekcji” – panel zapisuje id sekcji, paszport po otwarciu przewija do niej (raz).
 */
let pending: string | null = null

export function requestPassportJump(id: string) {
  pending = id
}

export function consumePassportJump(): string | null {
  const id = pending
  pending = null
  return id
}
