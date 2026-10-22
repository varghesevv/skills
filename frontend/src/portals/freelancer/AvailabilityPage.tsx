import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import {
  addUnavailability,
  deleteUnavailability,
  listUnavailability,
  updateUnavailability,
} from '../../api/freelancer'
import type { Unavailability } from '../../api/types'
import { t } from '../../i18n'
import { formatDateTime, fromLocalInput, toLocalInput } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import { Alert, QueryBoundary, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import type { FieldErrors } from '../../shared/validation'
import MonthCalendar from './MonthCalendar'

const KEY = ['freelancer', 'unavailability'] as const

function PeriodForm({ editing, onDone }: { editing: Unavailability | null; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [from, setFrom] = useState(editing ? toLocalInput(editing.unavailable_from) : '')
  const [to, setTo] = useState(editing ? toLocalInput(editing.unavailable_to) : '')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: (body: { unavailable_from: string; unavailable_to: string }) =>
      editing ? updateUnavailability(editing.id, body) : addUnavailability(body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: KEY })
      if (!editing) {
        setFrom('')
        setTo('')
      }
      onDone()
    },
    onError: (error) => setFormError(errorMessage(error)),
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const start = fromLocalInput(from)
    const end = fromLocalInput(to)
    const found: FieldErrors = {}
    if (!start) found.from = t('validation.periodRequired')
    if (!end) found.to = t('validation.periodRequired')
    if (start && end && new Date(start) >= new Date(end)) found.to = t('validation.periodOrder')
    setErrors(found)
    if (start && end && Object.keys(found).length === 0) {
      save.mutate({ unavailable_from: start, unavailable_to: end })
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card form-grid cols-2">
      <h2 className="span-2">{editing ? t('availability.edit') : t('availability.add')}</h2>
      {formError && (
        <div className="span-2">
          <Alert kind="error" focus>
            {formError}
          </Alert>
        </div>
      )}
      <TextField
        label={t('availability.from')}
        name="from"
        type="datetime-local"
        value={from}
        onChange={setFrom}
        error={errors.from}
      />
      <TextField
        label={t('availability.to')}
        name="to"
        type="datetime-local"
        value={to}
        onChange={setTo}
        error={errors.to}
      />
      <div className="span-2 row-actions">
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {editing ? t('availability.submitEdit') : t('availability.submitAdd')}
        </button>
        {editing && (
          <button type="button" className="btn btn-quiet" onClick={onDone}>
            {t('common.cancel')}
          </button>
        )}
      </div>
    </form>
  )
}

function PeriodRow({
  period,
  onEdit,
}: {
  period: Unavailability
  onEdit: (period: Unavailability) => void
}) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const remove = useMutation({
    mutationFn: () => deleteUnavailability(period.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
    onError: (failure) => {
      setConfirming(false)
      setError(errorMessage(failure))
    },
  })

  return (
    <li className="card period">
      <p className="period-dates">
        <strong>{formatDateTime(period.unavailable_from)}</strong>
        <span aria-hidden="true"> → </span>
        <span className="sr-only"> {t('availability.to')} </span>
        <strong>{formatDateTime(period.unavailable_to)}</strong>
      </p>
      {error && <Alert kind="error">{error}</Alert>}
      <div className="row-actions">
        <button type="button" className="btn btn-quiet" onClick={() => onEdit(period)}>
          {t('common.edit')}
        </button>
        {confirming ? (
          <>
            <button
              type="button"
              className="btn btn-danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {t('common.confirmDelete')}
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </button>
          </>
        ) : (
          <button type="button" className="btn btn-quiet" onClick={() => setConfirming(true)}>
            {t('common.delete')}
          </button>
        )}
      </div>
    </li>
  )
}

export default function AvailabilityPage() {
  usePageTitle(t('availability.title'))
  const query = useQuery({ queryKey: KEY, queryFn: listUnavailability })
  const [editing, setEditing] = useState<Unavailability | null>(null)

  return (
    <>
      <h1>{t('availability.title')}</h1>
      <p className="lead">{t('availability.lead')}</p>
      <QueryBoundary query={query}>
        {(periods) => (
          <div className="availability-layout">
            <div className="stack">
              <PeriodForm
                key={editing?.id ?? 'new'}
                editing={editing}
                onDone={() => setEditing(null)}
              />
              <h2>{t('availability.list')}</h2>
              {periods.length === 0 ? (
                <p className="muted">{t('availability.empty')}</p>
              ) : (
                <ul className="stack plain-list">
                  {periods.map((period) => (
                    <PeriodRow key={period.id} period={period} onEdit={setEditing} />
                  ))}
                </ul>
              )}
            </div>
            <MonthCalendar periods={periods} />
          </div>
        )}
      </QueryBoundary>
    </>
  )
}
