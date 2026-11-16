import { useId, useRef, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import type { NavLinkItem } from './nav'

/** The menu of one group of links (docs/design-system.md, section 3.3). With `panel` it is a
 *  heading over an open list (inside the mobile Menu panel); without, a button that shows the
 *  list. A disclosure, not role="menu": Esc closes it and returns focus to the button, and focus
 *  leaving the group closes it. */
export default function GroupMenu({
  group,
  panel = false,
  onNavigate,
  children,
}: {
  group: { id: string; label: string; links: NavLinkItem[] }
  panel?: boolean
  onNavigate?: () => void
  /** Extra content under the links (the address and Log out of the account menu). */
  children?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const box = useRef<HTMLDivElement>(null)
  const shown = panel || open
  return (
    <div
      className={`navgroup${panel ? ' navgroup--panel' : ''}`}
      data-open={shown}
      ref={box}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          setOpen(false)
          box.current?.querySelector('button')?.focus()
        }
      }}
      onBlur={(event) => {
        if (!panel && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
      }}
    >
      {panel ? (
        <h2 className="navgroup-title">{group.label}</h2>
      ) : (
        <button
          type="button"
          className="btn btn-quiet"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen(!open)}
        >
          {group.label}
        </button>
      )}
      <ul id={id} className="navgroup-list plain-list">
        {group.links.map((link) => (
          <li key={link.to}>
            <NavLink
              to={link.to}
              onClick={() => {
                setOpen(false)
                onNavigate?.()
              }}
            >
              {link.label}
            </NavLink>
          </li>
        ))}
        {children}
      </ul>
    </div>
  )
}
