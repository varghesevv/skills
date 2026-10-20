import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

describe('App', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the app name and the API status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }),
    )
    renderApp()
    expect(screen.getByRole('heading', { name: 'Skills' })).toBeInTheDocument()
    expect(await screen.findByText(/API status:\s*ok/)).toBeInTheDocument()
  })

  it('shows unavailable when the API fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    renderApp()
    expect(await screen.findByText(/unavailable/)).toBeInTheDocument()
  })
})
