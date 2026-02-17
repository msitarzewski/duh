import { Badge } from '@/components/shared'

const providerColors: Record<string, 'cyan' | 'green' | 'amber' | 'red'> = {
  anthropic: 'cyan',
  openai: 'green',
  google: 'amber',
  mistral: 'red',
}

export function ModelBadge({ model }: { model: string }) {
  const provider = model.split(':')[0] ?? ''
  const variant = providerColors[provider] ?? 'default'

  return (
    <Badge variant={variant} size="sm">
      {model}
    </Badge>
  )
}
