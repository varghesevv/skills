import { useQuery } from '@tanstack/react-query'

import { fetchHealth } from './api/client'

export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: false })

  return (
    <main style={{ maxWidth: 640, margin: '4rem auto', padding: '0 1rem', fontFamily: 'sans-serif' }}>
      <h1>Skills</h1>
      <p>Find skilled freelancers, or offer your skills.</p>
      <p role="status">
        API status:{' '}
        {health.isPending ? 'checking…' : health.isError ? 'unavailable' : health.data.status}
      </p>
    </main>
  )
}
