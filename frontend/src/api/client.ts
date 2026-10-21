// Placeholder. From phase 3 on, replace with a client generated from the backend OpenAPI schema
// (docs/specification/04-api.md). Do not hand-write request types for endpoints.

export type HealthResponse = { status: string }

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/health')
  if (!response.ok) {
    throw new Error(`API health check failed with status ${response.status}`)
  }
  return (await response.json()) as HealthResponse
}
