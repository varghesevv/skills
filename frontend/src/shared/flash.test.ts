import { afterEach, describe, expect, it } from 'vitest'

import { clearFlash, setFlash, takeFlash } from './flash'

describe('the flash message', () => {
  afterEach(clearFlash)

  it('is there for every page that mounts while it is fresh', () => {
    setFlash('Done.')
    expect(takeFlash()).toBe('Done.')
    expect(takeFlash()).toBe('Done.')
  })

  it('is dropped once it is old, and replaced by a newer one', () => {
    setFlash('Old.')
    expect(takeFlash(Date.now() + 60_000)).toBeNull()
    expect(takeFlash()).toBeNull()
    setFlash('First.')
    setFlash('Second.')
    expect(takeFlash()).toBe('Second.')
  })

  it('is empty until something is set', () => {
    expect(takeFlash()).toBeNull()
  })
})
