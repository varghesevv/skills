import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { getRefreshToken } from '../../auth/tokenStore'
import {
  PASSWORD,
  apiError,
  json,
  makeMe,
  makePerson,
  mockApi,
  renderApp,
  signedInAs,
  tokens,
} from '../../testUtils'

// Generated for each run: a link token is a secret, so none is written into the source.
const LINK_TOKEN = `tok-${Math.random().toString(36).slice(2).padEnd(24, 'x')}`

type User = ReturnType<typeof userEvent.setup>

const CHURCHES = {
  items: [
    { id: 'church-1', name: 'Grace Church' },
    { id: 'church-2', name: 'Hope Church' },
  ],
}
const GROUPS = {
  items: [
    { id: 'group-1', name: 'Riverside', leader_name: 'Lena Leader' },
    { id: 'group-2', name: 'Hilltop', leader_name: 'Hari Host' },
  ],
}
const OTHER_GROUPS = { items: [{ id: 'group-9', name: 'Harbour', leader_name: 'Hana Leader' }] }

async function fillDetails(user: User) {
  await user.type(screen.getByLabelText('Full name'), 'Nadia Applicant')
  await user.type(screen.getByLabelText('Email'), 'n@example.com')
  await user.type(screen.getByLabelText('Mobile number'), '+971 50 000 0002')
  await user.type(screen.getByLabelText('New password'), PASSWORD)
}

/** The vouching section of the applicant home asks for these; the older tests are not about it. */
const VOUCHING_QUIET = {
  'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
  'GET /me/vouches': () => json(200, { items: [] }),
}

const next = (user: User) => user.click(screen.getByRole('button', { name: 'Next' }))

describe('sign in', () => {
  it('sends no account type and lands on the home of the person', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      'POST /auth/login': () => json(200, tokens('1')),
      'GET /me': () => json(200, makePerson()),
    })
    renderApp('/sign-in')
    await user.type(screen.getByLabelText('Email'), 'n@example.com')
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('heading', { name: 'Your application' })).toBeVisible()
    expect(api.last('POST /auth/login')?.body).toEqual({
      email: 'n@example.com',
      password: PASSWORD,
    })
    expect(getRefreshToken()).toBe('refresh-1')
  })

  it('says so when the details are wrong, without hinting which one', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({ 'POST /auth/login': () => apiError(401, 'invalid_credentials') })
    renderApp('/sign-in')
    await user.type(screen.getByLabelText('Email'), 'n@example.com')
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/email or password/i)
  })

  it('asks for both fields before it calls the server', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({})
    renderApp('/sign-in')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(api.count('POST /auth/login')).toBe(0)
    expect(screen.getAllByText(/required|valid email/i).length).toBeGreaterThan(0)
  })

  it('is offered on the landing page next to joining', async () => {
    mockApi({})
    renderApp('/')
    const main = within(await screen.findByRole('main'))
    expect(main.getByRole('link', { name: 'Join' })).toHaveAttribute('href', '/sign-up')
    expect(main.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in')
  })

  it('has a forgot password link that does not ask for an account type', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({ 'POST /auth/forgot-password': () => json(202, { status: 'accepted' }) })
    renderApp('/sign-in')
    await user.click(screen.getByRole('link', { name: /forgot/i }))
    expect(screen.queryByLabelText('I am a')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Email'), 'n@example.com')
    await user.click(screen.getByRole('button', { name: /send/i }))
    await waitFor(() => expect(api.count('POST /auth/forgot-password')).toBe(1))
    expect(api.last('POST /auth/forgot-password')?.body).toEqual({
      email: 'n@example.com',
      user_type: 'person',
    })
  })
})

describe('sign up', () => {
  it('walks through details, church, home group and what to do, then sends one request', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      'GET /churches': () => json(200, CHURCHES),
      'GET /churches/church-1/home-groups': () => json(200, GROUPS),
      'POST /auth/signup': () => json(201, { id: 'x', status: 'pending' }),
    })
    renderApp('/sign-up')
    expect(screen.getByText(/Step 1 of 4/)).toBeVisible()
    await fillDetails(user)
    await next(user)

    await user.click(await screen.findByLabelText('Grace Church'))
    await next(user)
    expect(screen.getByText(/Step 3 of 4/)).toBeVisible()
    expect(await screen.findByText(/Led by Hari Host/)).toBeVisible()
    await user.click(screen.getByLabelText(/Hilltop/))
    await next(user)

    await user.click(screen.getByLabelText(/offer my skills/))
    await user.click(screen.getByRole('button', { name: 'Send my application' }))

    expect(await screen.findByRole('heading', { name: 'Thank you' })).toBeVisible()
    expect(api.count('POST /auth/signup')).toBe(1)
    expect(api.last('POST /auth/signup')?.body).toEqual({
      full_name: 'Nadia Applicant',
      email: 'n@example.com',
      mobile_number: '+971500000002',
      password: PASSWORD,
      requested_status: 'provider',
      home_group_id: 'group-2',
    })
  })

  it('does not go on until the details are valid or a choice is made', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({ 'GET /churches': () => json(200, CHURCHES) })
    renderApp('/sign-up')
    await user.type(screen.getByLabelText('Full name'), 'Nadia Applicant')
    await user.type(screen.getByLabelText('Email'), 'n@example.com')
    await user.type(screen.getByLabelText('Mobile number'), '+971500000002')
    await user.type(screen.getByLabelText('New password'), 'short')
    await next(user)
    expect(screen.getByText(/at least 10 characters/i, { selector: '.field-error' })).toBeVisible()
    expect(screen.getByText(/Step 1 of 4/)).toBeVisible()

    await user.clear(screen.getByLabelText('New password'))
    await user.type(screen.getByLabelText('New password'), PASSWORD)
    await next(user)
    await screen.findByLabelText('Grace Church')
    await next(user) // no church chosen
    expect(screen.getByRole('alert')).toHaveTextContent(/choose your organisation/i)
    expect(api.count('POST /auth/signup')).toBe(0)
  })

  it('can go back and keeps what was typed', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({ 'GET /churches': () => json(200, CHURCHES) })
    renderApp('/sign-up')
    await fillDetails(user)
    await next(user)
    await user.click(await screen.findByRole('button', { name: 'Back' }))
    expect(screen.getByLabelText('Full name')).toHaveValue('Nadia Applicant')
    expect(screen.getByLabelText('Email')).toHaveValue('n@example.com')
  })

  it('says when an account already exists, without saying which detail matched', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({
      'GET /churches': () => json(200, CHURCHES),
      'GET /churches/church-1/home-groups': () => json(200, GROUPS),
      'POST /auth/signup': () => apiError(409, 'account_exists'),
    })
    renderApp('/sign-up')
    await fillDetails(user)
    await next(user)
    await user.click(await screen.findByLabelText('Grace Church'))
    await next(user)
    await user.click(await screen.findByLabelText(/Riverside/))
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Send my application' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i)
    expect(screen.queryByRole('heading', { name: 'Thank you' })).toBeNull()
  })

  it('shows a message when a group is no longer available', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({
      'GET /churches': () => json(200, CHURCHES),
      'GET /churches/church-1/home-groups': () => json(200, GROUPS),
      'POST /auth/signup': () => apiError(422, 'invalid_choice'),
    })
    renderApp('/sign-up')
    await fillDetails(user)
    await next(user)
    await user.click(await screen.findByLabelText('Grace Church'))
    await next(user)
    await user.click(await screen.findByLabelText(/Riverside/))
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Send my application' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/not available/i)
  })

  it('tells people the church list is empty instead of leaving them stuck', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({ 'GET /churches': () => json(200, { items: [] }) })
    renderApp('/sign-up')
    await fillDetails(user)
    await next(user)
    expect(await screen.findByText(/no organisation to join yet/i)).toBeVisible()
  })
})

describe('sign up with an invitation link', () => {
  it('skips the church and group and joins the group of the link', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      'POST /group-invitations/lookup': () =>
        json(200, {
          church_name: 'Grace Church',
          home_group_name: 'Riverside',
          leader_name: 'Lena Leader',
        }),
      'POST /auth/signup': () => json(201, { id: 'x', status: 'pending' }),
    })
    renderApp(`/join/${LINK_TOKEN}`)
    expect(
      await screen.findByText(/invited to Riverside in Grace Church, led by Lena Leader/),
    ).toBeVisible()
    expect(screen.getByText(/Step 1 of 2/)).toBeVisible()
    expect(api.last('POST /group-invitations/lookup')?.body).toEqual({
      token: LINK_TOKEN,
    })
    await fillDetails(user)
    await next(user)
    await user.click(screen.getByRole('button', { name: 'Send my application' }))

    expect(await screen.findByRole('heading', { name: 'Thank you' })).toBeVisible()
    const body = api.last('POST /auth/signup')?.body as Record<string, unknown>
    expect(body.invitation_token).toBe(LINK_TOKEN)
    expect(body).not.toHaveProperty('home_group_id')
    expect(api.count('GET /churches')).toBe(0)
  })

  it('offers to choose a group when the link does not work', async () => {
    mockApi({ 'POST /group-invitations/lookup': () => apiError(404, 'not_found') })
    renderApp(`/join/${LINK_TOKEN}`)
    expect(await screen.findByText(/invitation link is not valid/i)).toBeVisible()
    expect(screen.getByRole('link', { name: /Choose my home group/ })).toHaveAttribute(
      'href',
      '/sign-up',
    )
  })

  it('keeps the token out of the address of every request', async () => {
    const api = mockApi({ 'POST /group-invitations/lookup': () => apiError(404, 'not_found') })
    renderApp(`/join/${LINK_TOKEN}`)
    await screen.findByText(/invitation link is not valid/i)
    expect(api.calls.every((call) => !call.key.includes(LINK_TOKEN))).toBe(true)
  })
})

describe('the home of a person by status', () => {
  it('shows an applicant where they applied and the vouches so far', async () => {
    signedInAs(makeMe(), { 'GET /me': () => json(200, makePerson({ vouch_count: 1 })) })
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'Your application' })).toBeVisible()
    expect(screen.getByText('Grace Church')).toBeVisible()
    expect(screen.getByText('Riverside')).toBeVisible()
    expect(screen.getByText('Lena Leader')).toBeVisible()
    expect(screen.getByText('1 vouch')).toBeVisible()
  })

  it('shows a revoked person that they have no access, and nothing else', async () => {
    signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'revoked', home_group: null, leader: null })),
    })
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'No access' })).toBeVisible()
    expect(screen.queryByRole('button', { name: /close my account/i })).toBeNull()
  })

  it('welcomes an admitted person with their status', async () => {
    signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'provider', full_name: 'Pia Provider' })),
    })
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'Welcome, Pia Provider' })).toBeVisible()
    expect(screen.getByText('Your status: Freelancer')).toBeVisible()
  })

  it('needs a login', async () => {
    mockApi({})
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible()
  })

  it('keeps a person out of the portals of the older accounts and the other way round', async () => {
    signedInAs(makeMe(), { 'GET /me': () => json(200, makePerson()) })
    renderApp('/freelancer')
    expect(await screen.findByRole('heading', { name: 'Your application' })).toBeVisible()
  })

  it('sends an older account that opens the person home to its own portal', async () => {
    signedInAs()
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'Welcome, Fatima Khan' })).toBeVisible()
  })
})

describe('change of choice and leaving', () => {
  // The vouch panels on the same page ask for these.
  const vouching = {
    'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
    'GET /me/vouches': () => json(200, { items: [] }),
    'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
  }
  const routes = {
    ...vouching,
    'GET /churches': () => json(200, CHURCHES),
    'GET /churches/church-1/home-groups': () => json(200, GROUPS),
    'GET /churches/church-2/home-groups': () => json(200, OTHER_GROUPS),
  }

  it('moves an applicant to another group and shows the new leader', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, makePerson()),
      'PUT /me/application': () =>
        json(
          200,
          makePerson({
            home_group: { id: 'group-2', name: 'Hilltop' },
            leader: { name: 'Hari Host' },
          }),
        ),
    })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    await user.selectOptions(
      await screen.findByLabelText('Home group'),
      'Hilltop (Led by Hari Host)',
    )
    await user.click(screen.getByRole('button', { name: 'Save my choice' }))
    expect(await screen.findByText('Your choice was saved.')).toBeVisible()
    expect(api.last('PUT /me/application')?.body).toEqual({
      home_group_id: 'group-2',
      requested_status: 'searcher',
    })
    expect(await screen.findByText('Hari Host')).toBeVisible()
  })

  it('changes only what they apply for', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, makePerson()),
      'PUT /me/application': () => json(200, makePerson({ requested_status: 'provider' })),
    })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    expect(screen.getByRole('button', { name: 'Save my choice' })).toBeDisabled()
    await user.click(screen.getByLabelText(/offer my skills/))
    await user.click(screen.getByRole('button', { name: 'Save my choice' }))
    await screen.findByText('Your choice was saved.')
    expect(api.last('PUT /me/application')?.body).toEqual({ requested_status: 'provider' })
  })

  it('does not let them save a new church without choosing one of its groups', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), { ...routes, 'GET /me': () => json(200, makePerson()) })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    await user.selectOptions(await screen.findByLabelText('Another organisation'), 'church-2')
    expect(screen.getByRole('button', { name: 'Save my choice' })).toBeDisabled()
    await user.selectOptions(
      await screen.findByLabelText('Home group'),
      'Harbour (Led by Hana Leader)',
    )
    expect(screen.getByRole('button', { name: 'Save my choice' })).toBeEnabled()
  })

  it('says when the application was decided in the meantime', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, makePerson()),
      'PUT /me/application': () => apiError(409, 'not_pending'),
    })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    await user.click(screen.getByLabelText(/offer my skills/))
    await user.click(screen.getByRole('button', { name: 'Save my choice' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already been decided/i)
  })

  it('closes the account after the password is asked again, then signs out', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, makePerson()),
      'DELETE /me': () => json(204),
    })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    expect(screen.queryByRole('button', { name: 'Close my account' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'I want to leave' }))
    await user.type(screen.getByLabelText('Your password, to confirm'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Close my account' }))

    await waitFor(() => expect(api.count('DELETE /me')).toBe(1))
    expect(api.last('DELETE /me')?.body).toEqual({ password: PASSWORD })
    expect(await screen.findByRole('link', { name: 'Join' })).toBeVisible()
    expect(getRefreshToken()).toBeNull()
  })

  it('stays signed in and says so when the password is wrong', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, makePerson()),
      'DELETE /me': () => apiError(403, 'invalid_password'),
    })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    await user.click(screen.getByRole('button', { name: 'I want to leave' }))
    await user.type(screen.getByLabelText('Your password, to confirm'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Close my account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/password is not correct/i)
    expect(screen.getByRole('heading', { name: 'Your application' })).toBeVisible()
  })

  it('does not call the server without a password', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), { ...routes, 'GET /me': () => json(200, makePerson()) })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    await user.click(screen.getByRole('button', { name: 'I want to leave' }))
    await user.click(screen.getByRole('button', { name: 'Close my account' }))
    expect(api.count('DELETE /me')).toBe(0)
  })
})

describe('change of choice: loading, empty and error states', () => {
  // The vouch panels on the same page ask for these.
  const vouching = {
    'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
    'GET /me/vouches': () => json(200, { items: [] }),
    'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
  }
  it('says so when the churches cannot be loaded, and offers to try again', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(makeMe(), {
      ...vouching,
      ...VOUCHING_QUIET,
      'GET /me': () => json(200, makePerson()),
      'GET /churches': () =>
        ++attempts === 1 ? apiError(503, 'service_unavailable') : json(200, CHURCHES),
      'GET /churches/church-1/home-groups': () => json(200, GROUPS),
    })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable|try again/i)
    expect(screen.getByRole('button', { name: 'Save my choice' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  })

  it('says when another church has no home group to join', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...vouching,
      'GET /me': () => json(200, makePerson()),
      'GET /churches': () => json(200, CHURCHES),
      'GET /churches/church-1/home-groups': () => json(200, GROUPS),
      'GET /churches/church-2/home-groups': () => json(200, { items: [] }),
    })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    await user.selectOptions(await screen.findByLabelText('Another organisation'), 'church-2')
    expect(await screen.findByText(/no home group to join yet/i)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Save my choice' })).toBeDisabled()
  })
})

describe('leaving: focus and cancelling', () => {
  // The vouch panels on the same page ask for these.
  const vouching = {
    'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
    'GET /me/vouches': () => json(200, { items: [] }),
    'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
  }
  const routes = {
    ...vouching,
    'GET /churches': () => json(200, CHURCHES),
    'GET /churches/church-1/home-groups': () => json(200, GROUPS),
  }

  it('moves focus to the confirmation and gives it back when cancelled', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), { ...routes, 'GET /me': () => json(200, makePerson()) })
    renderApp('/member')
    await screen.findByRole('heading', { name: 'Your application' })
    await user.click(screen.getByRole('button', { name: 'I want to leave' }))
    expect(screen.getByRole('group', { name: 'Leave' })).toHaveFocus()
    await user.type(screen.getByLabelText('Your password, to confirm'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'I want to leave' })).toHaveFocus(),
    )
    expect(screen.queryByLabelText('Your password, to confirm')).toBeNull()
    expect(api.count('DELETE /me')).toBe(0)
  })
})
