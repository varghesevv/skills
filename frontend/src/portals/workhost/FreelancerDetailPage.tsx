import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import type { FreelancerPublic, LabelType } from '../../api/types'
import { vouchFor } from '../../api/organisation'
import { createRating, getFreelancer, updateRating } from '../../api/workhost'
import { useUser } from '../../auth/AuthContext'
import { t, type StringKey } from '../../i18n'
import { formatDateTime } from '../../shared/dates'
import { errorMessage } from '../../shared/errors'
import RatingsList from '../../shared/RatingsList'
import { Alert, Badge, QueryBoundary, SelectField, TextAreaField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import { ratingSchema, validate, type FieldErrors } from '../../shared/validation'
import { VOUCHED_KEY } from '../organisation/keys'
import { GIVEN_KEY } from './GivenRatingsPage'
import type { Portal } from './SearchPage'
import { formatRate } from './format'

const detailKey = (id: string) => ['freelancer-public', id] as const

const OTHER_GROUPS: readonly { type: LabelType; title: StringKey }[] = [
  { type: 'language', title: 'labels.language' },
  { type: 'timing', title: 'labels.timing' },
  { type: 'nativity', title: 'labels.nativity' },
]

const SCORES = Array.from({ length: 10 }, (_, index) => {
  const value = String(index + 1)
  return { value, label: value }
})

function RatingForm({ person }: { person: FreelancerPublic }) {
  const queryClient = useQueryClient()
  const existing = person.my_rating
  const [score, setScore] = useState(existing ? String(existing.rating) : '')
  const [comment, setComment] = useState(existing?.comment ?? '')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const save = useMutation({
    mutationFn: (body: { rating: number; comment: string | null }) =>
      existing ? updateRating(existing.id, body) : createRating(person.id, body),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: detailKey(person.id) }),
        queryClient.invalidateQueries({ queryKey: ['ratings', person.id] }),
        queryClient.invalidateQueries({ queryKey: GIVEN_KEY }),
      ])
      setSaved(true)
    },
    onError: (error) => setFormError(errorMessage(error)),
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    setSaved(false)
    const result = validate(ratingSchema, { rating: score, comment })
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    save.mutate({ rating: result.data.rating, comment: result.data.comment || null })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card form-grid">
      <h2>{existing ? t('rate.edit') : t('rate.new')}</h2>
      {formError && (
        <Alert kind="error" focus>
          {formError}
        </Alert>
      )}
      {saved && <Alert kind="success">{t('rate.saved')}</Alert>}
      <SelectField
        label={t('rate.score')}
        name="rating"
        value={score}
        onChange={(value) => {
          setSaved(false)
          setScore(value)
        }}
        options={[{ value: '', label: t('rate.choose') }, ...SCORES]}
        error={errors.rating}
      />
      <TextAreaField
        label={t('rate.comment')}
        name="comment"
        maxLength={2000}
        value={comment}
        onChange={(value) => {
          setSaved(false)
          setComment(value)
        }}
        error={errors.comment}
      />
      <button type="submit" className="btn btn-primary" disabled={save.isPending}>
        {save.isPending
          ? t('common.saving')
          : existing
            ? t('rate.submitEdit')
            : t('rate.submitNew')}
      </button>
    </form>
  )
}

function Profile({ person, portal }: { person: FreelancerPublic; portal: Portal }) {
  const skills = person.labels.filter((item) => item.label.label_type === 'skill')
  return (
    <div className="stack">
      <section className="card" aria-labelledby="facts-heading">
        <h2 id="facts-heading">{t('detail.rate')}</h2>
        <dl className="facts">
          <div>
            <dt>{t('detail.rate')}</dt>
            <dd>
              {formatRate(person.rate_per_hour, person.rate_currency)}{' '}
              {person.is_rate_negotiable && <Badge tone="good">{t('search.negotiableTag')}</Badge>}
            </dd>
          </div>
          <div>
            <dt>{t('detail.rating')}</dt>
            <dd>
              {person.average_rating === null
                ? t('search.noRatings')
                : t('search.average', {
                    average: person.average_rating.toFixed(1),
                    count: person.rating_count,
                  })}
            </dd>
          </div>
          <div>
            <dt>{t('detail.nationality')}</dt>
            <dd>{person.nationality ?? t('common.none')}</dd>
          </div>
          <div>
            <dt>{t('detail.language')}</dt>
            <dd>{person.primary_language ?? t('common.none')}</dd>
          </div>
        </dl>
      </section>

      {portal === 'workhost' && (
        <section className="card" aria-labelledby="contact-heading">
          <h2 id="contact-heading">{t('detail.contact')}</h2>
          <dl className="facts">
            <div>
              <dt>{t('detail.mobile')}</dt>
              <dd>
                {person.mobile_number ? (
                  <a href={`tel:${person.mobile_number}`}>{person.mobile_number}</a>
                ) : (
                  t('common.none')
                )}
              </dd>
            </div>
            <div>
              <dt>WhatsApp</dt>
              <dd>
                {person.whatsapp_availability ? t('detail.whatsapp') : t('detail.noWhatsapp')}
              </dd>
            </div>
          </dl>
        </section>
      )}

      <section className="card" aria-labelledby="labels-heading">
        <h2 id="labels-heading">{t('detail.labels')}</h2>
        {person.labels.length === 0 && <p className="muted">{t('detail.noLabels')}</p>}
        {skills.length > 0 && (
          <>
            <h3>{t('labels.skill')}</h3>
            <ul className="chips plain-list">
              {skills.map((item) => (
                <li key={item.label.id} className="chip">
                  {item.label.label_name}
                  {item.level && <span className="muted"> · {item.level.label_name}</span>}
                </li>
              ))}
            </ul>
          </>
        )}
        {OTHER_GROUPS.map((group) => {
          const items = person.labels.filter((item) => item.label.label_type === group.type)
          if (items.length === 0) return null
          return (
            <div key={group.type}>
              <h3>{t(group.title)}</h3>
              <ul className="chips plain-list">
                {items.map((item) => (
                  <li key={item.label.id} className="chip">
                    {item.label.label_name}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </section>

      <section className="card" aria-labelledby="vouch-heading">
        <h2 id="vouch-heading">{t('detail.vouchedBy')}</h2>
        {person.vouched_by.length === 0 ? (
          <p className="muted">{t('detail.noVouches')}</p>
        ) : (
          <ul className="chips plain-list">
            {person.vouched_by.map((org) => (
              <li key={org.org_id} className="chip">
                {org.org_name}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card" aria-labelledby="unavailable-heading">
        <h2 id="unavailable-heading">{t('detail.unavailable')}</h2>
        {person.unavailable.length === 0 ? (
          <p className="muted">{t('detail.alwaysAvailable')}</p>
        ) : (
          <ul className="plain-list">
            {person.unavailable.map((period) => (
              <li key={period.id}>
                {formatDateTime(period.unavailable_from)} → {formatDateTime(period.unavailable_to)}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function VouchPanel({ person }: { person: FreelancerPublic }) {
  const user = useUser()
  const queryClient = useQueryClient()
  const approved = user.approval_status === 'approved'
  const alreadyShown = person.vouched_by.some((org) => org.org_id === user.id)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const vouch = useMutation({
    mutationFn: () => vouchFor(person.id),
    onSuccess: async () => {
      setSent(true)
      await queryClient.invalidateQueries({ queryKey: VOUCHED_KEY })
    },
    onError: (failure) => setError(errorMessage(failure)),
  })

  return (
    <section className="card form-grid" aria-labelledby="vouch-action-heading">
      <h2 id="vouch-action-heading">{t('vouch.heading')}</h2>
      {error && (
        <Alert kind="error" focus>
          {error}
        </Alert>
      )}
      {sent && <Alert kind="success">{t('vouch.sent')}</Alert>}
      {!approved && <Alert kind="info">{t('vouch.notApproved')}</Alert>}
      {alreadyShown ? (
        <p>{t('vouch.already')}</p>
      ) : (
        <button
          type="button"
          className="btn btn-primary"
          disabled={!approved || vouch.isPending || sent}
          onClick={() => {
            setError(null)
            vouch.mutate()
          }}
        >
          {vouch.isPending ? t('common.saving') : t('vouch.action')}
        </button>
      )}
      <p>
        <Link to="/organisation/freelancers">{t('vouch.viewList')}</Link>
      </p>
    </section>
  )
}

export default function FreelancerDetailPage({ portal }: { portal: Portal }) {
  const { id = '' } = useParams()
  const location = useLocation()
  const search = (location.state as { search?: string } | null)?.search ?? ''
  const query = useQuery({ queryKey: detailKey(id), queryFn: () => getFreelancer(id) })
  usePageTitle(query.data?.full_name ?? t('search.noName'))

  return (
    <>
      <p>
        <Link to={`/${portal}/search${search ? `?${search}` : ''}`}>← {t('detail.back')}</Link>
      </p>
      <QueryBoundary query={query}>
        {(person) => (
          <>
            <h1>{person.full_name ?? t('search.noName')}</h1>
            <div className="detail-layout">
              <Profile person={person} portal={portal} />
              <div className="stack">
                {portal === 'workhost' ? (
                  <RatingForm key={person.id} person={person} />
                ) : (
                  <VouchPanel key={person.id} person={person} />
                )}
                <h2>{t('detail.ratings')}</h2>
                <RatingsList freelancerId={person.id} />
              </div>
            </div>
          </>
        )}
      </QueryBoundary>
    </>
  )
}
