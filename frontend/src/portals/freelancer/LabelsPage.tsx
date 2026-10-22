import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { getProfile, listLabels, replaceLabels } from '../../api/freelancer'
import type { FreelancerProfile, LabelOut, LabelType } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { errorMessage } from '../../shared/errors'
import { Alert, QueryBoundary } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { PROFILE_KEY } from './ProfilePage'

const LABELS_KEY = ['labels'] as const

type GroupType = Exclude<LabelType, 'skill_level'>

const GROUPS: readonly { type: GroupType; title: StringKey }[] = [
  { type: 'skill', title: 'labels.skill' },
  { type: 'language', title: 'labels.language' },
  { type: 'timing', title: 'labels.timing' },
  { type: 'nativity', title: 'labels.nativity' },
]

/** Levels such as "basic", "50%", "80%": words first, then by number. */
export function sortLevels(levels: LabelOut[]): LabelOut[] {
  const rank = (label: LabelOut) => {
    const number = Number.parseInt(label.label_name, 10)
    return Number.isNaN(number) ? -1 : number
  }
  return [...levels].sort((a, b) => rank(a) - rank(b) || a.label_name.localeCompare(b.label_name))
}

// label id -> chosen level id (or null)
type Selection = Record<string, string | null>

function initialSelection(profile: FreelancerProfile, available: LabelOut[]): Selection {
  // A label an admin has since switched off cannot be saved again, so it is dropped here.
  const activeIds = new Set(available.map((label) => label.id))
  const selection: Selection = {}
  for (const item of profile.labels) {
    if (activeIds.has(item.label.id)) {
      selection[item.label.id] = item.level && activeIds.has(item.level.id) ? item.level.id : null
    }
  }
  return selection
}

function LabelsForm({ profile, labels }: { profile: FreelancerProfile; labels: LabelOut[] }) {
  const queryClient = useQueryClient()
  const [selection, setSelection] = useState(() => initialSelection(profile, labels))
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const levels = sortLevels(labels.filter((label) => label.label_type === 'skill_level'))

  const save = useMutation({
    mutationFn: () =>
      replaceLabels(
        Object.entries(selection).map(([label_id, level_label_id]) => ({
          label_id,
          level_label_id,
        })),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROFILE_KEY })
      setSaved(true)
    },
    onError: (error) => setFormError(errorMessage(error)),
  })

  function toggle(id: string, checked: boolean) {
    setSaved(false)
    setSelection((current) => {
      const next = { ...current }
      if (checked) next[id] = null
      else delete next[id]
      return next
    })
  }

  function setLevel(id: string, level: string) {
    setSaved(false)
    setSelection((current) => ({ ...current, [id]: level === '' ? null : level }))
  }

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault()
        setFormError(null)
        setSaved(false)
        save.mutate()
      }}
    >
      {formError && (
        <Alert kind="error" focus>
          {formError}
        </Alert>
      )}
      {saved && <Alert kind="success">{t('common.saved')}</Alert>}

      {GROUPS.map((group) => {
        const items = labels.filter((label) => label.label_type === group.type)
        const count = items.filter((label) => label.id in selection).length
        return (
          <fieldset key={group.type} className="card label-group">
            <legend>
              {t(group.title)} <span className="muted">({t('labels.selected', { count })})</span>
            </legend>
            {items.length === 0 ? (
              <p className="muted">{t('labels.empty')}</p>
            ) : (
              <ul className="check-grid">
                {items.map((label) => {
                  const checked = label.id in selection
                  const checkId = `label-${label.id}`
                  return (
                    <li key={label.id} className="check-item">
                      <div className="field field-check">
                        <input
                          id={checkId}
                          type="checkbox"
                          checked={checked}
                          onChange={(event) => toggle(label.id, event.target.checked)}
                        />
                        <label htmlFor={checkId}>{label.label_name}</label>
                      </div>
                      {group.type === 'skill' && checked && (
                        <select
                          aria-label={t('labels.level', { skill: label.label_name })}
                          value={selection[label.id] ?? ''}
                          onChange={(event) => setLevel(label.id, event.target.value)}
                        >
                          <option value="">{t('labels.noLevel')}</option>
                          {levels.map((level) => (
                            <option key={level.id} value={level.id}>
                              {level.label_name}
                            </option>
                          ))}
                        </select>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </fieldset>
        )
      })}

      <button type="submit" className="btn btn-primary" disabled={save.isPending}>
        {save.isPending ? t('common.saving') : t('common.save')}
      </button>
    </form>
  )
}

export default function LabelsPage() {
  usePageTitle(t('labels.title'))
  const profile = useQuery({ queryKey: PROFILE_KEY, queryFn: getProfile })
  const labels = useQuery({ queryKey: LABELS_KEY, queryFn: listLabels })
  return (
    <>
      <h1>{t('labels.title')}</h1>
      <p className="lead">{t('labels.lead')}</p>
      <QueryBoundary query={profile}>
        {(me) => (
          <QueryBoundary query={labels}>
            {(available) => <LabelsForm key={me.id} profile={me} labels={available} />}
          </QueryBoundary>
        )}
      </QueryBoundary>
    </>
  )
}
