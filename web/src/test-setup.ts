import '@testing-library/jest-dom/vitest'

// Provide localStorage for zustand persist middleware in happy-dom
if (typeof globalThis.localStorage === 'undefined' || !globalThis.localStorage?.setItem) {
  const store: Record<string, string> = {}
  const localStorageMock = {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { Object.keys(store).forEach(k => delete store[k]) },
    get length() { return Object.keys(store).length },
    key: (index: number) => Object.keys(store)[index] ?? null,
  }
  Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true, configurable: true })
}
