import { Droplet, Layers, Leaf, Mountain, Waves, type LucideIcon } from 'lucide-react'

/** Warstwy mapy (SPEC 5.3) – jedna główna naraz. */
export type LayerKey = 'kondycja' | 'wilgotnosc' | 'teren' | 'splyw' | 'gleba'

export type LegendSpec =
  | { kind: 'gradient'; colors: string[]; left: string; right: string; note?: string }
  | { kind: 'classes'; items: { color: string; label: string }[]; note?: string }
  | { kind: 'symbols'; items: { symbol: 'arrow' | 'spot' | 'outflow' | 'line' | 'pin'; label: string }[] }

export const LAYERS: { key: LayerKey; label: string; short: string; icon: LucideIcon; legend: LegendSpec }[] = [
  {
    key: 'kondycja',
    label: 'Kondycja upraw',
    short: 'Kondycja',
    icon: Leaf,
    legend: {
      kind: 'gradient',
      colors: ['#C8453B', '#E8B931', '#5BB37F', '#1F4D33'],
      left: 'Słaba roślinność',
      right: 'Bujna',
      note: 'Białe = chmury lub brak zdjęcia',
    },
  },
  {
    key: 'wilgotnosc',
    label: 'Wilgotność roślin',
    short: 'Wilgotność',
    icon: Droplet,
    legend: { kind: 'gradient', colors: ['#8B6B4A', '#E9DCC3', '#2F80C9'], left: 'Sucho', right: 'Wilgotno' },
  },
  {
    key: 'teren',
    label: 'Teren',
    short: 'Teren',
    icon: Mountain,
    legend: {
      kind: 'classes',
      items: [
        { color: '#8B6B4A', label: 'Sucha górka' },
        { color: '#E9DCC3', label: 'Stok' },
        { color: '#9DB5A0', label: 'Płasko' },
        { color: '#2F80C9', label: 'Mokry dołek' },
      ],
    },
  },
  {
    key: 'splyw',
    label: 'Spływ wody',
    short: 'Spływ',
    icon: Waves,
    legend: {
      kind: 'symbols',
      items: [
        { symbol: 'arrow', label: 'Kierunek spływu' },
        { symbol: 'spot', label: 'Tu zbiera się woda' },
        { symbol: 'outflow', label: 'Tu woda ucieka' },
        { symbol: 'line', label: 'Rowy, cieki, zbiorniki' },
        { symbol: 'pin', label: 'Zgłoszenia rolników' },
      ],
    },
  },
  {
    key: 'gleba',
    label: 'Gleba',
    short: 'Gleba',
    icon: Layers,
    legend: {
      kind: 'classes',
      items: [
        { color: '#F2D64B', label: 'I – bardzo podatna na suszę' },
        { color: '#F0A04B', label: 'II – podatna' },
        { color: '#D9722E', label: 'III – średnio podatna' },
        { color: '#9C3D2A', label: 'IV – mało podatna' },
        { color: '#8E918F', label: 'Gleby organiczne' },
      ],
    },
  },
]

export const layerByKey = (k: LayerKey) => LAYERS.find((l) => l.key === k)!
