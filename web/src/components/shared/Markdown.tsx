import { useEffect, useRef, useState, type ComponentPropsWithoutRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark-dimmed.css'

function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!ref.current) return
    let cancelled = false

    import('mermaid').then(({ default: mermaid }) => {
      if (cancelled) return
      mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          primaryColor: '#00d4ff',
          primaryTextColor: '#e4e4e7',
          primaryBorderColor: '#00d4ff40',
          lineColor: '#52525b',
          secondaryColor: '#1a1a2e',
          tertiaryColor: '#0a0a0f',
          fontFamily: 'JetBrains Mono, monospace',
        },
      })
      const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`
      return mermaid.render(id, code)
    }).then((result) => {
      if (cancelled || !result || !ref.current) return
      ref.current.innerHTML = result.svg
    }).catch(() => {
      if (!cancelled) setError(true)
    })

    return () => { cancelled = true }
  }, [code])

  if (error) {
    return (
      <pre className="my-3 rounded-lg overflow-x-auto bg-[rgba(0,0,0,0.4)] border border-[rgba(255,255,255,0.06)] p-4 text-sm leading-relaxed">
        <code>{code}</code>
      </pre>
    )
  }

  return <div ref={ref} className="my-4 flex justify-center [&_svg]:max-w-full" />
}

interface MarkdownProps {
  children: string
  className?: string
}

export function Markdown({ children, className = '' }: MarkdownProps) {
  return (
    <div className={`duh-prose ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          code({ className: codeClassName, children: codeChildren, ...rest }) {
            const isInline = !codeClassName
            const match = /language-(\w+)/.exec(codeClassName || '')

            if (!isInline && match?.[1] === 'mermaid') {
              return <MermaidBlock code={String(codeChildren).replace(/\n$/, '')} />
            }

            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-[rgba(255,255,255,0.06)] text-[var(--color-primary)] font-mono text-[0.85em]"
                  {...rest as ComponentPropsWithoutRef<'code'>}
                >
                  {codeChildren}
                </code>
              )
            }

            return (
              <code className={codeClassName} {...rest as ComponentPropsWithoutRef<'code'>}>
                {codeChildren}
              </code>
            )
          },
          pre({ children: preChildren }) {
            return (
              <pre className="my-3 rounded-lg overflow-x-auto bg-[rgba(0,0,0,0.4)] border border-[rgba(255,255,255,0.06)] p-4 text-sm leading-relaxed">
                {preChildren}
              </pre>
            )
          },
          table({ children: tableChildren }) {
            return (
              <div className="my-3 overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  {tableChildren}
                </table>
              </div>
            )
          },
          th({ children: thChildren }) {
            return (
              <th className="text-left px-3 py-2 border-b border-[rgba(255,255,255,0.1)] text-[var(--color-text)] font-semibold text-xs font-mono">
                {thChildren}
              </th>
            )
          },
          td({ children: tdChildren }) {
            return (
              <td className="px-3 py-2 border-b border-[rgba(255,255,255,0.05)] text-[var(--color-text-secondary)]">
                {tdChildren}
              </td>
            )
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
