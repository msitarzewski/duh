import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RefinementPanel } from '@/components/consensus/RefinementPanel'
import type { ClarifyingQuestion } from '@/api/types'

const questions: ClarifyingQuestion[] = [
  { question: 'What is the expected scale?', hint: 'users per day' },
  { question: 'What is your budget?', hint: null },
  { question: 'Any existing infrastructure?', hint: 'cloud provider' },
]

describe('RefinementPanel', () => {
  it('renders all tabs', () => {
    render(
      <RefinementPanel
        questions={questions}
        answers={{}}
        onAnswer={vi.fn()}
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    expect(screen.getByText('Q1')).toBeInTheDocument()
    expect(screen.getByText('Q2')).toBeInTheDocument()
    expect(screen.getByText('Q3')).toBeInTheDocument()
  })

  it('shows first question by default', () => {
    render(
      <RefinementPanel
        questions={questions}
        answers={{}}
        onAnswer={vi.fn()}
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    expect(screen.getByText('What is the expected scale?')).toBeInTheDocument()
    expect(screen.getByText('users per day')).toBeInTheDocument()
  })

  it('switches tab on click', () => {
    render(
      <RefinementPanel
        questions={questions}
        answers={{}}
        onAnswer={vi.fn()}
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByText('Q2'))
    expect(screen.getByText('What is your budget?')).toBeInTheDocument()
  })

  it('submit disabled when not all answered', () => {
    render(
      <RefinementPanel
        questions={questions}
        answers={{ 0: 'answer1' }}
        onAnswer={vi.fn()}
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    const submitBtn = screen.getByText('Start Consensus')
    expect(submitBtn).toBeDisabled()
  })

  it('submit enabled when all answered', () => {
    render(
      <RefinementPanel
        questions={questions}
        answers={{ 0: 'a', 1: 'b', 2: 'c' }}
        onAnswer={vi.fn()}
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    const submitBtn = screen.getByText('Start Consensus')
    expect(submitBtn).not.toBeDisabled()
  })

  it('calls onSubmit when submit clicked', () => {
    const onSubmit = vi.fn()
    render(
      <RefinementPanel
        questions={questions}
        answers={{ 0: 'a', 1: 'b', 2: 'c' }}
        onAnswer={vi.fn()}
        onSubmit={onSubmit}
        onSkip={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByText('Start Consensus'))
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('calls onSkip when skip clicked', () => {
    const onSkip = vi.fn()
    render(
      <RefinementPanel
        questions={questions}
        answers={{}}
        onAnswer={vi.fn()}
        onSubmit={vi.fn()}
        onSkip={onSkip}
      />,
    )
    fireEvent.click(screen.getByText('Skip'))
    expect(onSkip).toHaveBeenCalledOnce()
  })

  it('calls onAnswer when typing', () => {
    const onAnswer = vi.fn()
    render(
      <RefinementPanel
        questions={questions}
        answers={{}}
        onAnswer={onAnswer}
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    const textarea = screen.getByPlaceholderText('Your answer...')
    fireEvent.change(textarea, { target: { value: 'test answer' } })
    expect(onAnswer).toHaveBeenCalledWith(0, 'test answer')
  })

  it('shows checkmark on answered tabs', () => {
    const { container } = render(
      <RefinementPanel
        questions={questions}
        answers={{ 0: 'answered', 1: '', 2: 'also answered' }}
        onAnswer={vi.fn()}
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
      />,
    )
    // Tabs with answers should have SVG checkmarks
    const svgs = container.querySelectorAll('svg')
    expect(svgs).toHaveLength(2)
  })
})
