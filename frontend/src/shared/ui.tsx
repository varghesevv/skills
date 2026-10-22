import type { UseQueryResult } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState, type HTMLAttributes, type ReactNode } from 'react'

import { t } from '../i18n'
import { errorMessage } from './errors'

type FieldShared = {
  label: string
  name: string
  value: string
  onChange: (value: string) => void
  error?: string
  hint?: string
  className?: string
}

type TextFieldProps = FieldShared & {
  type?: 'text' | 'email' | 'tel' | 'password' | 'datetime-local'
  list?: string
  autoComplete?: string
  inputMode?: HTMLAttributes<HTMLInputElement>['inputMode']
  maxLength?: number
  adornment?: ReactNode
}

function describedBy(...ids: (string | false | undefined)[]): string | undefined {
  const joined = ids.filter(Boolean).join(' ')
  return joined || undefined
}

export function TextField(props: TextFieldProps) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  return (
    <div className={`field ${props.className ?? ''}`.trim()}>
      <label htmlFor={id}>{props.label}</label>
      <div className="input-row">
        <input
          id={id}
          name={props.name}
          type={props.type ?? 'text'}
          value={props.value}
          onChange={(event) => props.onChange(event.target.value)}
          autoComplete={props.autoComplete}
          inputMode={props.inputMode}
          maxLength={props.maxLength}
          list={props.list}
          aria-invalid={props.error ? true : undefined}
          aria-describedby={describedBy(props.hint && hintId, props.error && errorId)}
        />
        {props.adornment}
      </div>
      {props.hint && (
        <p className="field-hint" id={hintId}>
          {props.hint}
        </p>
      )}
      {props.error && (
        <p className="field-error" id={errorId}>
          {props.error}
        </p>
      )}
    </div>
  )
}

export function PasswordField(props: Omit<TextFieldProps, 'type' | 'adornment'>) {
  const [visible, setVisible] = useState(false)
  return (
    <TextField
      {...props}
      type={visible ? 'text' : 'password'}
      adornment={
        <button
          type="button"
          className="btn btn-quiet"
          aria-pressed={visible}
          onClick={() => setVisible((current) => !current)}
        >
          {visible ? t('field.hidePassword') : t('field.showPassword')}
        </button>
      }
    />
  )
}

export function SelectField(
  props: FieldShared & { options: readonly { value: string; label: string }[] },
) {
  const id = useId()
  const errorId = `${id}-error`
  return (
    <div className={`field ${props.className ?? ''}`.trim()}>
      <label htmlFor={id}>{props.label}</label>
      <select
        id={id}
        name={props.name}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        aria-invalid={props.error ? true : undefined}
        aria-describedby={describedBy(props.error && errorId)}
      >
        {props.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {props.error && (
        <p className="field-error" id={errorId}>
          {props.error}
        </p>
      )}
    </div>
  )
}

export function CheckboxField(props: {
  label: string
  name: string
  checked: boolean
  onChange: (checked: boolean) => void
  className?: string
}) {
  const id = useId()
  return (
    <div className={`field field-check ${props.className ?? ''}`.trim()}>
      <input
        id={id}
        name={props.name}
        type="checkbox"
        checked={props.checked}
        onChange={(event) => props.onChange(event.target.checked)}
      />
      <label htmlFor={id}>{props.label}</label>
    </div>
  )
}

export function Alert({
  kind,
  children,
  focus = false,
}: {
  kind: 'error' | 'success' | 'info'
  children: ReactNode
  /** Move keyboard focus to the message when it appears (after a failed submit). */
  focus?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (focus) ref.current?.focus()
  }, [focus])
  return (
    <div
      ref={ref}
      tabIndex={focus ? -1 : undefined}
      className={`alert alert-${kind}`}
      role={kind === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  )
}

export function LoadingScreen() {
  return (
    <div className="loading" role="status">
      {t('loading')}
    </div>
  )
}

/** Loading, error (with retry) and then the content, for a page that depends on one query. */
export function QueryBoundary<T>({
  query,
  children,
}: {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
}) {
  if (query.isPending) {
    return (
      <p role="status" className="muted">
        {t('loading')}
      </p>
    )
  }
  if (query.isError) {
    return (
      <Alert kind="error">
        <p>{errorMessage(query.error)}</p>
        <button type="button" className="btn btn-quiet" onClick={() => void query.refetch()}>
          {t('common.retry')}
        </button>
      </Alert>
    )
  }
  return <>{children(query.data)}</>
}

export function Pager({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number
  pageSize: number
  total: number
  onChange: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (pages <= 1) return null
  return (
    <nav className="pager" aria-label={t('common.page', { page, pages })}>
      <button
        type="button"
        className="btn btn-quiet"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        {t('common.previous')}
      </button>
      <span aria-live="polite">{t('common.page', { page, pages })}</span>
      <button
        type="button"
        className="btn btn-quiet"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        {t('common.next')}
      </button>
    </nav>
  )
}

export function Badge({
  tone,
  children,
}: {
  tone: 'neutral' | 'good' | 'warn'
  children: ReactNode
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function TextAreaField(props: FieldShared & { rows?: number; maxLength?: number }) {
  const id = useId()
  const errorId = `${id}-error`
  return (
    <div className={`field ${props.className ?? ''}`.trim()}>
      <label htmlFor={id}>{props.label}</label>
      <textarea
        id={id}
        name={props.name}
        rows={props.rows ?? 4}
        maxLength={props.maxLength}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        aria-invalid={props.error ? true : undefined}
        aria-describedby={describedBy(props.error && errorId)}
      />
      {props.error && (
        <p className="field-error" id={errorId}>
          {props.error}
        </p>
      )}
    </div>
  )
}
