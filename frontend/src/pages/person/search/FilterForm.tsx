import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { fetchHomeGroups } from '../../../api/person'
import type { IdName, LabelOut } from '../../../api/types'
import { t, type StringKey } from '../../../i18n'
import { SelectField, TextField } from '../../../shared/ui'
import type { FieldErrors } from '../../../shared/validation'
import { sortLevels } from '../provider/LabelsPage'
import { EMPTY_FILTERS, paramsFromValues, validateFilters, type FilterValues } from './searchParams'

/** A change of a typed value waits this long for the next key before the search is made. */
export const LIVE_DELAY_MS = 400

function CheckGroup({
  legend,
  options,
  selected,
  onChange,
  startOpen = false,
}: {
  legend: string
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
  startOpen?: boolean
}) {
  // A group starts open when it is the main one or already has choices; the rest can be opened.
  const [open, setOpen] = useState(startOpen || selected.length > 0)
  if (options.length === 0) return null
  return (
    <details
      className="filter-group"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {legend}
        {selected.length > 0 && <span className="muted"> ({selected.length})</span>}
      </summary>
      <fieldset className="plain-fieldset">
        <legend className="sr-only">{legend}</legend>
        <ul className="plain-list">
          {options.map((name) => {
            const id = `filter-${legend}-${name}`
            return (
              <li key={name} className="field field-check">
                <input
                  id={id}
                  type="checkbox"
                  checked={selected.includes(name)}
                  onChange={(event) =>
                    onChange(
                      event.target.checked
                        ? [...selected, name]
                        : selected.filter((item) => item !== name),
                    )
                  }
                />
                <label htmlFor={id}>{name}</label>
              </li>
            )
          })}
        </ul>
      </fieldset>
    </details>
  )
}

const RATING_OPTIONS = [
  { value: '', label: t('search.anyRating') },
  ...[5, 6, 7, 8, 9].map((rating) => ({
    value: String(rating),
    label: t('search.ratingAtLeast', { rating }),
  })),
]

const SORT_KEYS: { value: FilterValues['sort']; label: StringKey }[] = [
  { value: 'newest', label: 'search.sort.newest' },
  { value: 'rating', label: 'search.sort.rating' },
  { value: 'rate', label: 'search.sort.rate' },
]
export const SORT_OPTIONS = SORT_KEYS.map((item) => ({ value: item.value, label: t(item.label) }))

export default function FilterForm({
  labels,
  churches,
  initial,
  onApply,
  live = false,
}: {
  labels: LabelOut[]
  churches: IdName[]
  initial: FilterValues
  onApply: (values: FilterValues) => void
  /** Apply as the person changes a control (docs/design-system.md, section 2.3), on desktop. */
  live?: boolean
}) {
  const [values, setValues] = useState(initial)
  const latest = useRef(values)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  // The last filters this form applied itself, so that the address coming back is not mistaken
  // for a change made elsewhere (a chip, "clear all") that the form must show.
  const applied = useRef(paramsFromValues(initial).toString())
  const initialKey = paramsFromValues(initial).toString()
  useEffect(() => {
    if (initialKey === applied.current) return
    applied.current = initialKey
    clearTimeout(timer.current)
    latest.current = initial
    setValues(initial)
    setErrors({})
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only a new address matters
  }, [initialKey])
  useEffect(() => () => clearTimeout(timer.current), [])
  const [errors, setErrors] = useState<FieldErrors>({})
  // The groups of the chosen church; the filter is optional, so a failed load only hides it.
  const groups = useQuery({
    queryKey: ['church-groups', values.churchId],
    queryFn: () => fetchHomeGroups(values.churchId),
    enabled: values.churchId !== '',
  })

  const names = (type: LabelOut['label_type']) =>
    labels.filter((label) => label.label_type === type).map((label) => label.label_name)
  const levels = sortLevels(labels.filter((label) => label.label_type === 'skill_level'))

  function submit(next: FilterValues) {
    const found = validateFilters(next)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    applied.current = paramsFromValues(next).toString()
    onApply(next)
  }

  /** Takes the new values; in live mode also makes the search, at once or after a pause. */
  function change(next: FilterValues, typed: boolean) {
    latest.current = next
    setValues(next)
    if (!live) return
    clearTimeout(timer.current)
    if (typed) timer.current = setTimeout(() => submit(latest.current), LIVE_DELAY_MS)
    else submit(next)
  }

  function set<K extends keyof FilterValues>(name: K, value: FilterValues[K]) {
    const typed =
      typeof value === 'string' &&
      ['maxRate', 'currency', 'availableFrom', 'availableTo'].includes(name)
    change({ ...latest.current, [name]: value }, typed)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    clearTimeout(timer.current)
    submit(values)
  }

  // The same two buttons at the top (kept in view while scrolling) and at the bottom.
  const actions = (
    <div className="row-actions">
      {!live && (
        <button type="submit" className="btn btn-primary">
          {t('search.apply')}
        </button>
      )}
      <button
        type="button"
        className="btn btn-quiet"
        onClick={() => {
          clearTimeout(timer.current)
          setErrors({})
          const cleared = { ...EMPTY_FILTERS, sort: values.sort }
          latest.current = cleared
          setValues(cleared)
          applied.current = paramsFromValues(cleared).toString()
          onApply(cleared)
        }}
      >
        {t('search.clear')}
      </button>
    </div>
  )

  return (
    <form onSubmit={onSubmit} noValidate className="stack">
      <div className="filter-actions-top">{actions}</div>
      <CheckGroup
        legend={t('labels.skill')}
        options={names('skill')}
        selected={values.skills}
        startOpen
        onChange={(next) => set('skills', next)}
      />
      {values.skills.length > 1 && (
        <SelectField
          label={t('search.skillMatch')}
          name="skill_match"
          value={values.skillMatch}
          onChange={(value) => set('skillMatch', value === 'all' ? 'all' : 'any')}
          options={[
            { value: 'any', label: t('search.matchAny') },
            { value: 'all', label: t('search.matchAll') },
          ]}
        />
      )}
      <SelectField
        label={t('search.skillLevel')}
        name="skill_level"
        value={values.skillLevel}
        onChange={(value) => set('skillLevel', value)}
        options={[
          { value: '', label: t('search.anyLevel') },
          ...levels.map((level) => ({ value: level.label_name, label: level.label_name })),
        ]}
      />
      <CheckGroup
        legend={t('labels.language')}
        options={names('language')}
        selected={values.languages}
        onChange={(next) => set('languages', next)}
      />
      <CheckGroup
        legend={t('labels.timing')}
        options={names('timing')}
        selected={values.timings}
        onChange={(next) => set('timings', next)}
      />
      <CheckGroup
        legend={t('labels.nativity')}
        options={names('nativity')}
        selected={values.nativity}
        onChange={(next) => set('nativity', next)}
      />
      <TextField
        label={t('search.maxRate')}
        name="max_rate"
        inputMode="decimal"
        value={values.maxRate}
        onChange={(value) => set('maxRate', value)}
        error={errors.maxRate}
      />
      <TextField
        label={t('profile.currency')}
        name="currency"
        autoComplete="off"
        maxLength={3}
        hint={t('profile.currencyHint')}
        value={values.currency}
        onChange={(value) => set('currency', value)}
        error={errors.currency}
      />
      <div className="field field-check">
        <input
          id="filter-negotiable"
          type="checkbox"
          checked={values.negotiable}
          onChange={(event) => set('negotiable', event.target.checked)}
        />
        <label htmlFor="filter-negotiable">{t('search.negotiable')}</label>
      </div>
      <TextField
        label={t('search.availableFrom')}
        name="available_from"
        type="datetime-local"
        value={values.availableFrom}
        onChange={(value) => set('availableFrom', value)}
        error={errors.availableFrom}
      />
      <TextField
        label={t('search.availableTo')}
        name="available_to"
        type="datetime-local"
        value={values.availableTo}
        onChange={(value) => set('availableTo', value)}
        error={errors.availableTo}
      />
      <SelectField
        label={t('search.minRating')}
        name="min_rating"
        value={values.minRating}
        onChange={(value) => set('minRating', value)}
        options={RATING_OPTIONS}
      />
      {churches.length > 0 && (
        <SelectField
          label={t('search.church')}
          name="church_id"
          value={values.churchId}
          onChange={(value) =>
            change({ ...latest.current, churchId: value, homeGroupId: '' }, false)
          }
          options={[
            { value: '', label: t('search.anyChurch') },
            ...churches.map((item) => ({ value: item.id, label: item.name })),
          ]}
        />
      )}
      {values.churchId && groups.data && groups.data.items.length > 0 && (
        <SelectField
          label={t('search.group')}
          name="home_group_id"
          value={values.homeGroupId}
          onChange={(value) => set('homeGroupId', value)}
          options={[
            { value: '', label: t('search.anyGroup') },
            ...groups.data.items.map((item) => ({ value: item.id, label: item.name })),
          ]}
        />
      )}
      {!live && actions}
    </form>
  )
}
