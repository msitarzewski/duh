export function outcomeColor(outcome: string | null): string {
  switch (outcome) {
    case 'success': return '#00ff88'
    case 'failure': return '#ff3b4f'
    case 'partial': return '#ffb800'
    default: return '#00d4ff'
  }
}

export function categoryIndex(category: string | null, categories: string[]): number {
  if (!category) return 0
  const idx = categories.indexOf(category)
  return idx >= 0 ? idx : 0
}

export function genusIndex(genus: string | null, genera: string[]): number {
  if (!genus) return 0
  const idx = genera.indexOf(genus)
  return idx >= 0 ? idx : 0
}
