import { useState, type FormEvent } from 'react'

import type { LabelOut, OrgBrief } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { SelectField, TextField } from '../../shared/ui'
import type { FieldErrors } from '../../shared/validation'
import { sortLevels } from '../freelancer/LabelsPage'
import { EMPTY_FILTERS, validateFilters, type FilterValues } from './searchParams'

function CheckGroup({
  legend,
  options,
  selected,
  onChange,
}: {
  legend: string
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
}) {
  if (options.length === 0) return null
  return (
    <fieldset className="plain-fieldset">
      <legend>{legend}</legend>
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
  organisations,
  initial,
  onApply,
}: {
  labels: LabelOut[]
  organisations: OrgBrief[]
  initial: FilterValues
  onApply: (values: FilterValues) => void
}) {
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState<FieldErrors>({})

  const names = (type: LabelOut['label_type']) =>
    labels.filter((label) => label.label_type === type).map((label) => label.label_name)
  const levels = sortLevels(labels.filter((label) => label.label_type === 'skill_level'))

  function set<K extends keyof FilterValues>(name: K, value: FilterValues[K]) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const found = validateFilters(values)
    setErrors(found)
    if (Object.keys(found).length === 0) onApply(values)
  }

  return (
    <form onSubmit={onSubmit} noValidate className="stack">
      <CheckGroup
        legend={t('labels.skill')}
        options={names('skill')}
        selected={values.skills}
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
      {organisations.length > 0 && (
        <SelectField
          label={t('search.vouchedBy')}
          name="org_id"
          value={values.orgId}
          onChange={(value) => set('orgId', value)}
          options={[
            { value: '', label: t('search.anyOrg') },
            ...organisations.map((item) => ({ value: item.id, label: item.org_name })),
          ]}
        />
      )}
      <div className="row-actions">
        <button type="submit" className="btn btn-primary">
          {t('search.apply')}
        </button>
        <button
          type="button"
          className="btn btn-quiet"
          onClick={() => {
            setErrors({})
            setValues({ ...EMPTY_FILTERS, sort: values.sort })
            onApply({ ...EMPTY_FILTERS, sort: values.sort })
          }}
        >
          {t('search.clear')}
        </button>
      </div>
    </form>
  )
}
