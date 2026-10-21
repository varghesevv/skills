import { useQuery } from '@tanstack/react-query'

import { fetchHealth } from './api/client'

const pageStyle = {
  maxWidth: 640,
  margin: '4rem auto',
  padding: '0 1rem',
  fontFamily: 'sans-serif',
}

function statusText(isPending: boolean, isError: boolean, status?: string): string {
  if (isPending) return 'checking…'
  if (isError) return 'unavailable'
  return status ?? 'unknown'
}

export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })

  return (
    <main style={pageStyle}>
      <h1>Skills</h1>
      <p>Find skilled freelancers, or offer your skills.</p>
      <p role="status">
        API status: {statusText(health.isPending, health.isError, health.data?.status)}
      </p>
    </main>
  )
}
