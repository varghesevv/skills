import { useEffect, useRef, type ReactNode, type RefObject } from 'react'

import { t } from '../i18n'

/** Gives focus back to the control that opened a question, once the question is dropped, so a
 *  keyboard or screen-reader user does not fall to the top of the page. Put the returned ref on
 *  the opening button; pass whether the question is open. */
export function useReturnFocus<T extends HTMLElement>(open: boolean): RefObject<T> {
  const opener = useRef<T>(null)
  const wasOpen = useRef(false)
  useEffect(() => {
    if (!open && wasOpen.current) opener.current?.focus()
    wasOpen.current = open || wasOpen.current
  }, [open])
  return opener
}

/** A question that must be answered before something that cannot be undone: the warning gets focus
 *  when it appears, so it is read out, and the answer is a button for yes and one for no. */
export function Confirm({
  label,
  warning,
  confirmLabel,
  busy,
  confirmDisabled,
  onConfirm,
  onCancel,
  children,
}: {
  label: string
  warning: ReactNode
  confirmLabel: string
  busy?: boolean
  /** The answer is not allowed yet, for example until a successor is chosen. */
  confirmDisabled?: boolean
  onConfirm: () => void
  onCancel: () => void
  /** Anything the answer needs besides the warning, such as a choice of successor. */
  children?: ReactNode
}) {
  const text = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    text.current?.focus()
  }, [])
  return (
    <div className="span-2" role="group" aria-label={label}>
      <p ref={text} tabIndex={-1}>
        {warning}
      </p>
      {children}
      <div className="form-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || confirmDisabled}
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={onCancel}>
          {t('common.cancel')}
        </button>
      </div>
    </div>
  )
}
