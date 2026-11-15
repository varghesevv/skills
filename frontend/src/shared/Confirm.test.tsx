import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { Confirm, useReturnFocus } from './Confirm'

function Harness({ onConfirm }: { onConfirm: () => void }) {
  const [open, setOpen] = useState(false)
  const opener = useReturnFocus<HTMLButtonElement>(open)
  return open ? (
    <Confirm
      label="Close it"
      warning="This cannot be undone."
      confirmLabel="Yes, close it"
      onConfirm={onConfirm}
      onCancel={() => setOpen(false)}
    />
  ) : (
    <button ref={opener} type="button" onClick={() => setOpen(true)}>
      Close
    </button>
  )
}

describe('the confirmation question', () => {
  it('puts focus on the warning when it opens, and back on the button when it is dropped', async () => {
    const user = userEvent.setup({ delay: null })
    render(<Harness onConfirm={() => undefined} />)
    expect(screen.getByRole('button', { name: 'Close' })).not.toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.getByText('This cannot be undone.')).toHaveFocus()
    expect(screen.getByRole('group', { name: 'Close it' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
  })

  it('does not steal focus before anything was opened', () => {
    render(<Harness onConfirm={() => undefined} />)
    expect(document.body).toHaveFocus()
  })

  it('confirms only when the confirming button is pressed', async () => {
    const user = userEvent.setup({ delay: null })
    const confirm = vi.fn()
    render(<Harness onConfirm={confirm} />)
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(confirm).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Yes, close it' }))
    expect(confirm).toHaveBeenCalledTimes(1)
  })

  it('switches both buttons off while busy', () => {
    render(
      <Confirm
        label="L"
        warning="W"
        confirmLabel="Go"
        busy
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    )
    expect(screen.getByRole('button', { name: 'Go' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
  })
})
