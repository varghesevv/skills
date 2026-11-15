import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'

/** Gives the pages that came from the older portals the width of the other member pages. */
export default function Frame({ children }: { children?: ReactNode }) {
  return <div className="container">{children ?? <Outlet />}</div>
}
