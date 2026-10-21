// All user-visible text lives here so more languages can be added later (open question Q9).

const en = {
  'app.name': 'Skills',
  'skip.toContent': 'Skip to content',
  'nav.menu': 'Open menu',
  'nav.close': 'Close menu',
  'nav.main': 'Main navigation',
  'nav.dashboard': 'Dashboard',
  'nav.logIn': 'Log in',
  'nav.register': 'Register',
  'nav.logOut': 'Log out',
  'nav.home': 'Home',

  'role.freelancer': 'Freelancer',
  'role.workhost': 'Work host',
  'role.organisation': 'Organisation',
  'role.admin': 'Admin',

  'landing.title': 'Find skilled freelancers, or offer your skills',
  'landing.lead':
    'Freelancers show their skills, work hosts find the right person, and organisations vouch for the people they trust.',
  'landing.freelancer.title': 'I am a freelancer',
  'landing.freelancer.text': 'Show your skills and availability to work hosts.',
  'landing.workhost.title': 'I need to hire',
  'landing.workhost.text': 'Search freelancers by skill, rate and availability.',
  'landing.organisation.title': 'I represent an organisation',
  'landing.organisation.text': 'Vouch for freelancers. New organisations are approved by an admin.',
  'landing.toDashboard': 'Go to your dashboard',

  'field.email': 'Email',
  'field.mobile': 'Mobile number',
  'field.mobileHint': 'Digits only, with an optional + at the start.',
  'field.password': 'Password', // secret-scan:allow (a form label)
  'field.newPassword': 'New password',
  'field.passwordHint': 'At least 10 characters.',
  'field.userType': 'I am a',
  'field.orgName': 'Organisation name',
  'field.nationality': 'Nationality (optional)',
  'field.language': 'Primary language (optional)',
  'field.whatsapp': 'I am available on WhatsApp',
  'field.showPassword': 'Show password',
  'field.hidePassword': 'Hide password',

  'validation.required': 'This field is required.',
  'validation.email': 'Enter a valid email address.',
  'validation.mobile': 'Enter 7 to 15 digits, optionally starting with +.',
  'validation.passwordShort': 'Use at least 10 characters.',
  'validation.passwordLong': 'Use at most 128 characters.',
  'validation.orgName': 'Enter 2 to 200 characters.',
  'validation.tooLong': 'This text is too long.',

  'login.title': 'Log in',
  'login.submit': 'Log in',
  'login.working': 'Logging in…',
  'login.forgot': 'Forgot your password?',
  'login.noAccount': 'No account yet?',

  'register.title': 'Create an account',
  'register.choose': 'Choose the kind of account you need.',
  'register.freelancer.title': 'Create a freelancer account',
  'register.workhost.title': 'Create a work host account',
  'register.organisation.title': 'Create an organisation account',
  'register.submit': 'Create account',
  'register.working': 'Creating account…',
  'register.haveAccount': 'Already have an account?',
  'register.done.title': 'Account created',
  'register.done.text': 'You can now log in.',
  'register.done.pending':
    'Your organisation is waiting for admin approval. You can log in after it is approved.',
  'register.done.login': 'Go to log in',

  'forgot.title': 'Reset your password',
  'forgot.text': 'Enter your email and we will send a reset link if an account exists.',
  'forgot.submit': 'Send reset link',
  'forgot.working': 'Sending…',
  'forgot.done': 'If an account exists for that email, a reset link is on its way.',
  'forgot.back': 'Back to log in',

  'reset.title': 'Choose a new password',
  'reset.submit': 'Save new password',
  'reset.working': 'Saving…',
  'reset.done': 'Your password was changed. You can now log in.',
  'reset.missingToken': 'This reset link is incomplete. Request a new one.',
  'reset.requestNew': 'Request a new link',

  'dashboard.title': 'Dashboard',
  'dashboard.welcome': 'Welcome, {name}',
  'dashboard.account': 'Your account',
  'dashboard.email': 'Email',
  'dashboard.mobile': 'Mobile number',
  'dashboard.role': 'Account type',
  'dashboard.since': 'Member since',
  'dashboard.lead.freelancer': 'Your profile, availability and ratings will be managed here.',
  'dashboard.lead.workhost': 'Search freelancers and manage the ratings you give from here.',
  'dashboard.lead.organisation': 'Manage the freelancers you vouch for from here.',
  'dashboard.lead.admin': 'Reports, organisation approvals and labels are managed from here.',

  'notFound.title': 'Page not found',
  'notFound.text': 'The page you are looking for does not exist.',
  'notFound.back': 'Back to the start',

  loading: 'Loading…',

  'error.generic': 'Something went wrong. Please try again.',
  'error.network': 'Cannot reach the server. Check your connection and try again.',
  'error.unavailable': 'The service is temporarily unavailable. Please try again soon.',
  'error.invalidCredentials': 'Invalid email or password.',
  'error.organisationPending': 'This organisation is still waiting for admin approval.',
  'error.organisationRejected': 'This organisation was not approved.',
  'error.tooManyAttempts': 'Too many failed attempts. Try again in {minutes} minute(s).',
  'error.emailTaken': 'An account with this email already exists.',
  'error.invalidResetToken': 'This reset link is invalid or has expired. Request a new one.',
  'error.fixFields': 'Please correct the highlighted fields.',
} as const

export type StringKey = keyof typeof en

export function t(key: StringKey, params?: Record<string, string | number>): string {
  const template: string = en[key]
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  )
}
