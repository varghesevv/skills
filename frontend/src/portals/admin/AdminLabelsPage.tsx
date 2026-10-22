import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { createLabel, listAllLabels, updateLabel } from '../../api/admin'
import type { LabelOut, LabelType } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { errorMessage } from '../../shared/errors'
import { Alert, Badge, QueryBoundary, SelectField, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { labelNameSchema, validate } from '../../shared/validation'
import { ADMIN_LABELS_KEY } from './keys'

const TYPES: { type: LabelType; title: StringKey }[] = [
  { type: 'skill', title: 'labels.skill' },
  { type: 'skill_level', title: 'adminLabels.skillLevel' },
  { type: 'language', title: 'labels.language' },
  { type: 'timing', title: 'labels.timing' },
  { type: 'nativity', title: 'labels.nativity' },
]

function LabelRow({ item }: { item: LabelOut }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(item.label_name)
  const [nameError, setNameError] = useState<string | undefined>()
  const [error, setError] = useState<string | null>(null)

  const change = useMutation({
    mutationFn: (body: { label_name?: string; is_active?: boolean }) => updateLabel(item.id, body),
    onSuccess: async () => {
      setEditing(false)
      await queryClient.invalidateQueries({ queryKey: ADMIN_LABELS_KEY })
    },
    onError: (failure) => setError(errorMessage(failure)),
  })

  function saveName(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const result = validate(labelNameSchema, { label_name: name })
    if (!result.ok) {
      setNameError(result.errors.label_name)
      return
    }
    setNameError(undefined)
    change.mutate({ label_name: result.data.label_name })
  }

  return (
    <li className="card">
      {error && <Alert kind="error">{error}</Alert>}
      {editing ? (
        <form onSubmit={saveName} noValidate className="form-grid">
          <TextField
            label={t('adminLabels.name')}
            name={`name-${item.id}`}
            value={name}
            onChange={setName}
            error={nameError}
          />
          <div className="row-actions">
            <button type="submit" className="btn btn-primary" disabled={change.isPending}>
              {t('common.save')}
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => {
                setEditing(false)
                setName(item.label_name)
                setNameError(undefined)
              }}
            >
              {t('common.cancel')}
            </button>
          </div>
        </form>
      ) : (
        <>
          <div className="vouch-head">
            <h3>{item.label_name}</h3>
            {!item.is_active && <Badge tone="neutral">{t('adminLabels.inactive')}</Badge>}
          </div>
          <div className="row-actions">
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => setEditing(true)}
              aria-label={`${t('adminLabels.rename')}: ${item.label_name}`}
            >
              {t('adminLabels.rename')}
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              disabled={change.isPending}
              onClick={() => {
                setError(null)
                change.mutate({ is_active: !item.is_active })
              }}
              aria-label={`${item.is_active ? t('adminLabels.deactivate') : t('adminLabels.activate')}: ${item.label_name}`}
            >
              {item.is_active ? t('adminLabels.deactivate') : t('adminLabels.activate')}
            </button>
          </div>
        </>
      )}
    </li>
  )
}

function AddLabel({ type }: { type: LabelType }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState<string | undefined>()
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: createLabel,
    onSuccess: async () => {
      setName('')
      await queryClient.invalidateQueries({ queryKey: ADMIN_LABELS_KEY })
    },
    onError: (failure) => setError(errorMessage(failure)),
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    const result = validate(labelNameSchema, { label_name: name })
    if (!result.ok) {
      setNameError(result.errors.label_name)
      return
    }
    setNameError(undefined)
    create.mutate({ label_name: result.data.label_name, label_type: type })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card form-grid">
      <h2>{t('adminLabels.add')}</h2>
      {error && (
        <Alert kind="error" focus>
          {error}
        </Alert>
      )}
      <TextField
        label={t('adminLabels.newName')}
        name="new_label"
        value={name}
        onChange={setName}
        error={nameError}
      />
      <button type="submit" className="btn btn-primary" disabled={create.isPending}>
        {create.isPending ? t('common.saving') : t('adminLabels.addAction')}
      </button>
    </form>
  )
}

export default function AdminLabelsPage() {
  usePageTitle(t('adminLabels.title'))
  const [type, setType] = useState<LabelType>('skill')
  const query = useQuery({ queryKey: ADMIN_LABELS_KEY, queryFn: listAllLabels })

  return (
    <>
      <h1>{t('adminLabels.title')}</h1>
      <p className="lead">{t('adminLabels.lead')}</p>
      <SelectField
        label={t('adminLabels.kind')}
        name="label_type"
        value={type}
        onChange={(value) => setType(value as LabelType)}
        options={TYPES.map((item) => ({ value: item.type, label: t(item.title) }))}
      />
      <QueryBoundary query={query}>
        {(labels) => {
          const shown = labels.filter((item) => item.label_type === type)
          return (
            <div className="stack">
              <AddLabel key={type} type={type} />
              {shown.length === 0 ? (
                <p className="muted">{t('labels.empty')}</p>
              ) : (
                <ul className="stack plain-list">
                  {shown.map((item) => (
                    <LabelRow key={`${item.id}-${item.label_name}`} item={item} />
                  ))}
                </ul>
              )}
            </div>
          )
        }}
      </QueryBoundary>
    </>
  )
}
