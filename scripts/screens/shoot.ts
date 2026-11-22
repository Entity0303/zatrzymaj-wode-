/**
 * Zrzuty ekranu do prezentacji (Z1) – Playwright bez okna, na działającej lokalnie aplikacji (http://localhost:5173).
 * Tylko prawdziwe dane: bez ?dane=przykladowe; zrzut z napisem „DANE PRZYKŁADOWE” jest odrzucany.
 *
 *   cd scripts/screens && npm install && npx playwright install chromium
 *   npx tsx shoot.ts              – wszystkie zrzuty
 *   npx tsx shoot.ts 01-start 02-mapa-panel   – wybrane
 *
 * Komputer 1920×1080 @2x, telefon 390×844 @3x (isMobile, hasTouch); pl-PL, Europe/Warsaw, animacje wyłączone.
 * Przed zrzutem czekamy, aż analiza i zadania w tle się skończą (teren, satelita, tło suszowe, wody gruntowe):
 * znikają wskaźniki ładowania i napisy „Liczę… / Pobieram… / Szukam… / sprawdzam…” – najwyżej 60 s na działkę.
 */
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, type Browser, type BrowserContext, type Page } from 'playwright'

const BASE = process.env.SCREENS_BASE ?? 'http://localhost:5173'
const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'reports', 'screens')
const SETTLE_MS = 60_000

const DESKTOP = { viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 }
const MOBILE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }
const COMMON = { locale: 'pl-PL', timezoneId: 'Europe/Warsaw', reducedMotion: 'reduce' as const, colorScheme: 'light' as const }

const P1 = '201305_2.0038.6/1'
const P2 = '201305_2.0038.8/5'
/** Żuławy (Brzózki) – rów melioracyjny 12 m od działki; do warstwy „Rowy i zbiorniki” */
const P_WATER = '220907_5.0001.162'
const TODAY = { dzialka: P1, uprawa: 'zboza_ozime' }

/** Adres aplikacji z parametrami linku (lib/deepLink.ts): dzialka, uprawa, data, widok. */
function url(params: Record<string, string> = {}): string {
  const u = new URL(BASE)
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v)
  return u.href
}

/** Czy coś się jeszcze ładuje: aria-busy, kręciołki, napisy „Liczę… / Pobieram… / Szukam…” (kod jako tekst – dla przeglądarki). */
const BUSY = `(() => {
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 }
  if ([...document.querySelectorAll('[aria-busy="true"], .animate-spin')].some(visible)) return true
  return /Liczę|Pobieram|Szukam wody|Wczytuję|Analizuję|sprawdzam działki|liczę…|pobieram…|szukam…|Generuję/.test(document.body.innerText)
})()`

/** Czeka, aż przez 2,5 s nic się nie ładuje (zadania w tle startują po analizie); false = limit czasu. */
async function settle(page: Page, timeout = SETTLE_MS): Promise<boolean> {
  const start = Date.now()
  let quietSince: number | null = null
  while (Date.now() - start < timeout) {
    const isBusy = (await page.evaluate(BUSY).catch(() => true)) as boolean
    if (isBusy) quietSince = null
    else {
      quietSince ??= Date.now()
      if (Date.now() - quietSince >= 2500) return true
    }
    await page.waitForTimeout(500)
  }
  return false
}

async function settled(page: Page, timeout = SETTLE_MS) {
  if (!(await settle(page, timeout))) console.warn('  ! po limicie czasu coś nadal się ładuje – zrzut mimo to')
}

/** Kafle mapy i obrazy warstw dociągnięte. */
async function mapReady(page: Page) {
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
  await page.waitForTimeout(1200)
}

async function openParcel(page: Page, params: Record<string, string>) {
  await page.goto(url(params), { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: /Działka|Pole|Obszar/ }).first().waitFor({ timeout: 45_000 })
  await settled(page)
  await mapReady(page)
}

/** Menu „Warstwa mapy” → warstwa o podanej nazwie; potem czekamy na dane i kafle, legenda rozwinięta. */
async function pickLayer(page: Page, label: RegExp) {
  await page.getByRole('button', { name: /Warstwa mapy/ }).click()
  await page.getByRole('menuitemradio', { name: label }).click()
  await page.keyboard.press('Escape').catch(() => undefined)
  await settled(page)
  const legend = page.getByRole('button', { name: /Pokaż legendę/ })
  if (await legend.isVisible().catch(() => false)) await legend.click()
  await mapReady(page)
}

/** Przewija tak, żeby element z tym tekstem był u góry widocznej części panelu. */
async function scrollTo(page: Page, text: string | RegExp) {
  const el = page.getByText(text).first()
  await el.waitFor({ timeout: 20_000 })
  await el.evaluate((n) => n.scrollIntoView({ block: 'start' }))
  await page.waitForTimeout(400)
}

/** Rozwija sekcję panelu (przycisk-nagłówek), jeśli jest zwinięta. */
async function openSection(page: Page, name: RegExp) {
  const b = page.getByRole('button', { name }).first()
  await b.waitFor({ timeout: 20_000 })
  if ((await b.getAttribute('aria-expanded')) === 'false') await b.click()
  await page.waitForTimeout(300)
}

async function openPassport(page: Page, params: Record<string, string>, section: string) {
  await page.goto(url({ ...params, widok: 'paszport' }), { waitUntil: 'domcontentloaded' })
  await page.locator('#pp-werdykt:visible').first().waitFor({ timeout: 60_000 })
  await settled(page)
  const target = page.locator(`#${section}:visible`).first() // w dokumencie jest też ukryta kopia sekcji (do druku)
  await target.evaluate((n) => n.scrollIntoView({ block: 'start' }))
  await page.waitForTimeout(600)
  await settled(page, 20_000) // karta „Ceny i pogoda” dociąga dane po pokazaniu
  await target.evaluate((n) => n.scrollIntoView({ block: 'start' }))
  await page.waitForTimeout(400)
}

async function save(page: Page, name: string) {
  const text = (await page.evaluate('document.body.innerText')) as string
  if (/DANE PRZYKŁADOWE/i.test(text)) throw new Error(`${name}: na ekranie jest napis „DANE PRZYKŁADOWE” – zrzut odrzucony`)
  if (!page.context().browser()) throw new Error('przeglądarka zamknięta')
  const mobile = (page.viewportSize()?.width ?? 1920) < 600
  if (!mobile) await page.mouse.move(0, 0)
  await page.screenshot({ path: resolve(OUT, `${name}.png`), animations: 'disabled', caret: 'hide' })
  console.log(`  ✓ ${name}.png`)
}

/** Telefon: przestawia szufladę działki (zwinięty → do połowy → pełny) dotknięciem uchwytu, aż do wskazanego położenia. */
async function sheetTo(page: Page, state: RegExp) {
  const snap = page.getByRole('button', { name: /^Panel: / })
  for (let i = 0; i < 3 && !state.test((await snap.getAttribute('aria-label')) ?? ''); i++) {
    await snap.tap()
    await page.waitForTimeout(900)
  }
  await mapReady(page)
}

type Shot = { name: string; device: 'desktop' | 'mobile'; run: (page: Page) => Promise<void> }

const SHOTS: Shot[] = [
  {
    name: '01-start',
    device: 'desktop',
    run: async (page) => {
      await page.goto(url(), { waitUntil: 'domcontentloaded' })
      await page.getByRole('heading', { name: 'Wodoskop' }).first().waitFor({ timeout: 30_000 })
      await settle(page, 15_000)
      await mapReady(page)
    },
  },
  {
    // ortofoto, obrys, góra panelu z werdyktem (zapas wody i rekomendacje są niżej w panelu – zrzuty 10 i m3, paszport)
    name: '02-mapa-panel',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, TODAY)
    },
  },
  {
    name: '03-kondycja-upraw',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, TODAY)
      await pickLayer(page, /^Kondycja upraw/)
    },
  },
  {
    // aplikacja pokazuje jedną warstwę tematyczną naraz – tu „Spływ wody” (strzałki, miejsce odpływu)
    name: '04-teren-splyw',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, { dzialka: P2, uprawa: 'zboza_ozime' })
      await pickLayer(page, /^Spływ wody/)
    },
  },
  {
    name: '05-rowy-zbiorniki',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, { dzialka: P_WATER, uprawa: 'zboza_ozime' })
      await pickLayer(page, /^Rowy i zbiorniki/)
    },
  },
  {
    name: '06-susza-2018',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, { dzialka: P1, uprawa: 'zboza_ozime', data: '2018-06-30' })
      await openSection(page, /^Dlaczego\?/)
      await scrollTo(page, 'Tło suszowe w okolicy (EDO)')
    },
  },
  { name: '07-paszport-woda', device: 'desktop', run: (page) => openPassport(page, TODAY, 'pp-woda') },
  { name: '08-co-posiac', device: 'desktop', run: (page) => openPassport(page, TODAY, 'pp-posiac') },
  { name: '09-ceny-pogoda', device: 'desktop', run: (page) => openPassport(page, TODAY, 'pp-ceny') },
  {
    name: '10-wody-gruntowe',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, TODAY)
      await openSection(page, /^Dlaczego\?/)
      await scrollTo(page, /Wody gruntowe i /) // kafel A27 (tytuł w aplikacji: „Wody gruntowe i zapas z opadów”)
    },
  },
  {
    // pole narysowane ręcznie (4 narożniki przy działce) + lista działek ewidencyjnych pod polem
    name: '11-narysowane-pole',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, TODAY)
      await page.getByRole('button', { name: /Warstwa mapy/ }).click()
      await page.getByRole('menuitem', { name: /Narysuj swoje pole/ }).click()
      await page.getByRole('heading', { name: 'Narysuj swoje pole' }).waitFor({ timeout: 15_000 })
      for (const [x, y] of [[560, 420], [900, 380], [960, 620], [600, 680]] as const) {
        await page.mouse.click(x, y)
        await page.waitForTimeout(350)
      }
      await page.getByRole('button', { name: 'Gotowe' }).click()
      await page.getByText(/obrys narysowany na mapie/).first().waitFor({ timeout: 45_000 })
      await page
        .getByText(/Obejmuje działki:/)
        .first()
        .waitFor({ timeout: 8_000 })
        .catch(() => console.warn('  ! brak listy działek pod polem (panel na komputerze jej nie pokazuje)'))
      await settled(page)
      await mapReady(page)
    },
  },
  {
    // kreator zgłoszenia doprowadzony do podsumowania: adresat pisma i „Pobierz gotowe pismo”
    name: '12-zgloszenie-rowu',
    device: 'desktop',
    run: async (page) => {
      await openParcel(page, TODAY)
      await page.getByRole('button', { name: 'Zgłoszenia', exact: true }).click()
      await page.getByRole('radio', { name: 'Rów melioracyjny' }).click()
      await page.getByRole('button', { name: 'Dalej', exact: true }).click()
      await page.getByRole('radio', { name: 'Zarośnięty' }).click()
      await page.getByRole('radio', { name: 'Niski' }).click()
      await page.getByRole('button', { name: 'Dalej', exact: true }).click()
      await page.locator('#infra-description').fill('Rów przy drodze zarośnięty trzciną, woda po deszczu stoi na polu.')
      await page.getByRole('button', { name: /Dalej – podsumowanie/ }).click()
      await page.getByText('Do kogo skierować pismo').waitFor({ timeout: 15_000 })
      await settle(page, 20_000)
      await mapReady(page)
    },
  },
  { name: 'm1-mapa', device: 'mobile', run: (page) => openParcel(page, TODAY) },
  {
    // szuflada „do połowy”: mapa z działką u góry, nagłówek i werdykt u dołu
    name: 'm2-panel-wysuniety',
    device: 'mobile',
    run: async (page) => {
      await openParcel(page, TODAY)
      await sheetTo(page, /do połowy/)
    },
  },
  {
    // szuflada pełna: nagłówek działki, werdykt, formularz „Twoja działka”
    name: 'm3-werdykt',
    device: 'mobile',
    run: async (page) => {
      await openParcel(page, TODAY)
      await sheetTo(page, /pełny/)
    },
  },
  {
    // „Moje gospodarstwo”: cztery działki zapisane gwiazdką (prawdziwe analizy), dolny pasek rozwinięty;
    // po drodze zapisuje też ekran „Moje działki” jako 14-moje-dzialki.png
    name: '13-moje-gospodarstwo',
    device: 'desktop',
    run: async (page) => {
      for (const id of [P2, '302408_5.0017.70/4', P_WATER, P1]) {
        await openParcel(page, { dzialka: id, uprawa: 'zboza_ozime' })
        const star = page.getByRole('button', { name: 'Zapisz w Moich działkach' })
        if (await star.isVisible().catch(() => false)) await star.click()
        await page.waitForTimeout(500)
      }
      await page.getByRole('button', { name: 'Moje działki', exact: true }).click()
      await page.getByRole('heading', { name: /Moje działki/ }).first().waitFor({ timeout: 20_000 })
      await settled(page, 30_000)
      await save(page, '14-moje-dzialki')
      await openParcel(page, TODAY)
      await page.getByRole('button', { name: /^Moje gospodarstwo/ }).click()
      await settled(page, 30_000)
      await mapReady(page)
    },
  },
]

async function context(browser: Browser, device: Shot['device']): Promise<BrowserContext> {
  const ctx = await browser.newContext({ ...COMMON, ...(device === 'mobile' ? MOBILE : DESKTOP) })
  // czysta przeglądarka dla każdego zrzutu (bez zapisanych działek i ustawień z poprzednich przebiegów) –
  // czyszczenie raz na kontekst, nie przy każdej nawigacji w obrębie zrzutu
  await ctx.addInitScript({
    content:
      'try { if (!sessionStorage.getItem("__screens_clean")) { localStorage.clear(); sessionStorage.clear(); sessionStorage.setItem("__screens_clean", "1") } } catch (e) {}',
  })
  return ctx
}

async function main() {
  const wanted = process.argv.slice(2)
  const unknown = wanted.filter((w) => !SHOTS.some((s) => s.name === w))
  if (unknown.length) throw new Error(`Nieznane zrzuty: ${unknown.join(', ')}. Dostępne: ${SHOTS.map((s) => s.name).join(', ')}`)
  const shots = wanted.length ? SHOTS.filter((s) => wanted.includes(s.name)) : SHOTS
  mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  let failed = 0
  try {
    for (const shot of shots) {
      console.log(shot.name)
      const ctx = await context(browser, shot.device)
      const page = await ctx.newPage()
      try {
        await shot.run(page)
        await save(page, shot.name)
      } catch (e) {
        failed += 1
        console.error(`  ✗ ${shot.name}: ${(e as Error).message.split('\n')[0]}`)
      } finally {
        await ctx.close()
      }
    }
  } finally {
    await browser.close()
  }
  if (failed) process.exitCode = 1
}

await main()
