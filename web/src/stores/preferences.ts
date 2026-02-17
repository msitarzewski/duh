import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface PreferencesState {
  // Defaults
  defaultRounds: number
  defaultProtocol: 'consensus' | 'voting' | 'auto'
  costThreshold: number | null

  // UI
  soundEnabled: boolean

  // Actions
  setDefaultRounds: (rounds: number) => void
  setDefaultProtocol: (protocol: 'consensus' | 'voting' | 'auto') => void
  setCostThreshold: (threshold: number | null) => void
  setSoundEnabled: (enabled: boolean) => void
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      defaultRounds: 3,
      defaultProtocol: 'consensus',
      costThreshold: null,
      soundEnabled: false,

      setDefaultRounds: (rounds) => set({ defaultRounds: rounds }),
      setDefaultProtocol: (protocol) => set({ defaultProtocol: protocol }),
      setCostThreshold: (threshold) => set({ costThreshold: threshold }),
      setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),
    }),
    {
      name: 'duh-preferences',
    },
  ),
)
