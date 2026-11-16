import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import ProviderCard, { skillMatch } from './ProviderCard'
import { makeResult } from './testData'

// docs/design-system.md, sections 2.4 and 3.2.

const skills = (...names: string[]) => names.map((name) => ({ name, level: null }))

describe('skillMatch', () => {
  it('is nothing when no skill is searched', () => {
    expect(skillMatch({ skills: skills('welding') }, [])).toBeNull()
  })

  it('counts the searched skills the provider has, without regard to case', () => {
    const item = { skills: skills('Welding', 'plumbing') }
    expect(skillMatch(item, ['welding', 'Plumbing', 'carpentry'])).toEqual({ have: 2, of: 3 })
  })

  it('counts none, and counts a skill searched twice once', () => {
    expect(skillMatch({ skills: skills('welding') }, ['carpentry'])).toEqual({ have: 0, of: 1 })
    expect(skillMatch({ skills: skills('welding') }, ['welding', 'WELDING'])).toEqual({
      have: 1,
      of: 1,
    })
  })

  it('does not count a skill the provider lists twice', () => {
    expect(skillMatch({ skills: skills('welding', 'welding') }, ['welding'])).toEqual({
      have: 1,
      of: 1,
    })
  })
})

function show(props: Partial<Parameters<typeof ProviderCard>[0]> = {}) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ul>
          <ProviderCard
            item={makeResult({
              skills: skills('a', 'b', 'c', 'd', 'e', 'f'),
            })}
            search=""
            searchedSkills={['a', 'z']}
            matchAny
            own={false}
            {...props}
          />
        </ul>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProviderCard', () => {
  it('names the church and home group in one line, with the name as the link', () => {
    show()
    expect(screen.getByText('Grace Church · Riverside')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Anita Sharma' })).toHaveAttribute(
      'href',
      '/member/providers/22222222-2222-2222-2222-222222222222',
    )
  })

  it('shows four skills and says how many more', () => {
    show()
    const list = screen.getByRole('list', { name: 'Skills' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(5)
    expect(within(list).getByText('+2 more')).toBeInTheDocument()
  })

  it('shows the match only for "any"', () => {
    show()
    expect(screen.getByText('1 of 2 searched skills')).toBeInTheDocument()
  })

  it('shows no match for "all", and none when no skill is searched', () => {
    show({ matchAny: false })
    expect(screen.queryByText(/searched skills/)).toBeNull()
  })

  it('shows no match line without a search', () => {
    show({ searchedSkills: [] })
    expect(screen.queryByText(/searched skills/)).toBeNull()
  })

  it('has Reveal on another person and not on the person’s own card', () => {
    show()
    expect(screen.getByRole('button', { name: /Reveal the mobile number/ })).toBeInTheDocument()
  })

  it('has no Reveal on the own card', () => {
    show({ own: true })
    expect(screen.queryByRole('button', { name: /Reveal/ })).toBeNull()
  })
})
