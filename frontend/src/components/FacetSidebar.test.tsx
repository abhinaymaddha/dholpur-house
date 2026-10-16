import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it } from 'vitest'
import { facets } from '../test/fixtures'
import { emptyFilters, type Filters } from '../types'
import { FacetSidebar } from './FacetSidebar'

function Harness({ onFilters }: { onFilters: (f: Filters) => void }) {
  const [f, setF] = useState(emptyFilters())
  onFilters(f)
  return <FacetSidebar facets={facets()} filters={f} onChange={setF} />
}

it('drives every filter and toggles selections off again', async () => {
  let current = emptyFilters()
  render(<Harness onFilters={(f) => { current = f }} />)
  const u = userEvent.setup()

  await u.click(screen.getByRole('button', { name: /CSE 2025/ }))
  expect(current).toMatchObject({ cse_year: '2025', board: '' })
  await u.click(screen.getByRole('button', { name: /CSE 2025/ }))
  expect(current.cse_year).toBe('')

  await u.click(screen.getAllByRole('button', { name: /BB Swain/ })[0])
  expect(current).toMatchObject({ cse_year: '2025', board: 'BB Swain' })
  await u.click(screen.getAllByRole('button', { name: /BB Swain/ })[0])
  expect(current.board).toBe('')

  await u.click(screen.getByRole('button', { name: /Economy/ }))
  await u.click(screen.getByRole('button', { name: /Health/ }))
  expect(current.topics).toEqual(['Economy', 'Health'])
  await u.click(screen.getByRole('button', { name: /Economy/ }))
  expect(current.topics).toEqual(['Health'])

  await u.click(screen.getByRole('button', { name: /Engineering/ }))
  expect(current.background).toBe('Engineering')
  await u.click(screen.getByRole('button', { name: /Engineering/ }))
  expect(current.background).toBe('')

  expect(screen.queryByText('State 8')).toBeNull()
  await u.click(screen.getByRole('button', { name: 'Show all 8' }))
  expect(screen.getByText('State 8')).toBeInTheDocument()
  await u.click(screen.getByRole('button', { name: 'Show less' }))

  await u.click(screen.getByRole('checkbox'))
  expect(current.has_marks).toBe(true)
  await u.click(screen.getByRole('button', { name: /IFoS/ }))
  expect(current.exam).toBe('IFoS')
  await u.click(screen.getByRole('button', { name: /IFoS/ }))
  expect(current.exam).toBe('')

  await u.click(screen.getAllByRole('button', { name: 'Collapse' })[0])
  expect(screen.getAllByRole('button', { name: 'Expand' })).toHaveLength(1)
  await u.click(screen.getByRole('button', { name: 'Expand' }))
})

it('renders before facets arrive', () => {
  render(<FacetSidebar facets={null} filters={emptyFilters()} onChange={() => {}} />)
  expect(screen.getByText('Topics asked')).toBeInTheDocument()
})
