### Background

A scan of `frontend/src` on `main` (2026-11-27) found code, strings and styles that the web app never uses. Almost all of it was left behind by the older account types (freelancer, work host, organisation, platform admin), the older organisation-vouching screens, and the sidebar layout that the top menu bar replaced (PR #225). Every source file is still imported, and every dependency is used. Only the items below are dead.

The scan treated the following as used, and they must stay:
- Classes built at runtime, e.g. `` `alert-${kind}` `` and `` `badge-${tone}` `` in `shared/ui.tsx`.
- String keys built at runtime, e.g. `` t(`status.${…}`) ``, `` t(`privacy.${key}.title`) ``, `` t(`notifications.${kind}`) ``, `` t(`moves.state.${…}`) ``.

### Feature Criteria

1. **Unused strings (114 keys) are removed from `frontend/src/i18n/index.ts`:**
   - `register`: `register.title`, `register.choose`, `register.freelancer.title`, `register.workhost.title`, `register.organisation.title`, `register.submit`, `register.working`, `register.haveAccount`, `register.done.title`, `register.done.text`, `register.done.pending`, `register.done.login`
   - `login`: `login.title`, `login.noAccount`, `login.switch`, `login.org.title`, `login.org.text`, `login.admin.title`, `login.admin.text`
   - `landing`: `landing.freelancer.title`, `landing.freelancer.text`, `landing.workhost.title`, `landing.workhost.text`, `landing.organisation.title`, `landing.organisation.text`
   - `role`: `role.freelancer`, `role.workhost`, `role.organisation`, `role.admin`
   - `field`: `field.userType`, `field.orgName`, `field.nationality`, `field.language`
   - `dashboard`: `dashboard.shortcuts`, `dashboard.title`, `dashboard.welcome`, `dashboard.account`, `dashboard.email`, `dashboard.mobile`, `dashboard.role`, `dashboard.since`, `dashboard.lead.freelancer`, `dashboard.lead.workhost`, `dashboard.lead.organisation`, `dashboard.lead.admin`
   - `hostProfile`: `hostProfile.title`, `hostProfile.lead`, `hostProfile.days`
   - `orgProfile`: `orgProfile.title`, `orgProfile.lead`, `orgProfile.approval`, `orgProfile.status.pending`, `orgProfile.status.approved`, `orgProfile.status.rejected`
   - `adminOrgs`: `adminOrgs.title`, `adminOrgs.lead`, `adminOrgs.show`, `adminOrgs.pending`, `adminOrgs.approved`, `adminOrgs.rejected`, `adminOrgs.empty`, `adminOrgs.registered`, `adminOrgs.approve`, `adminOrgs.reject`
   - `vouches`: `vouches.title`, `vouches.lead`, `vouches.empty`, `vouches.accept`, `vouches.reject`, `vouches.since`, `vouches.status.pending`, `vouches.status.approved`, `vouches.status.revoked`, `vouches.inactive`
   - `vouched`: `vouched.title`, `vouched.lead`, `vouched.add`, `vouched.empty`, `vouched.since`, `vouched.status.pending`, `vouched.status.approved`, `vouched.status.revoked`, `vouched.revoke`, `vouched.confirm`, `vouched.again`
   - `vouch`: `vouch.heading`, `vouch.action`, `vouch.sent`, `vouch.already`, `vouch.notApproved`, `vouch.viewList` (the live `vouch.page.*` keys stay)
   - `reports`: `reports.title`, `reports.lead`, `reports.userType`, `reports.anyUserType`, `reports.organisation`
   - `days`: `days.sun`, `days.mon`, `days.tue`, `days.wed`, `days.thu`, `days.fri`, `days.sat`
   - `nav`: `nav.menu`, `nav.close`, `nav.vouches`, `nav.vouched`, `nav.orgs`, `nav.runs`, `nav.schedules` (the live `nav.menu.open` stays)
   - Single strings: `leader.applicant.vouchesFrom`, `leader.admit.working`, `signup.invitedChecking`, `invite.checking`
2. **Code that nothing uses is removed:**
   - `DAYS`, `Day` and `VouchStatus` in `api/types.ts`.
   - `profileNames` and `activeProfile` in `terminology/terms.ts`, and the variable `activeName` that only `activeProfile` reads (its assignments in `setProfile` go with it).
3. **Code that only tests use is removed, and its tests move to live schemas:**
   - Remove `loginSchema`, `freelancerRegisterSchema`, `workhostRegisterSchema` and `organisationRegisterSchema` in `shared/validation.ts`, and the two helpers only they use: `userType` and `registerBase`.
   - Their tests in `shared/validation.test.ts` also test the shared `validate()`, the cleanup of email and mobile number, and the error messages. Do not delete them; point them at the live schemas with the same fields: `signupDetailsSchema` (instead of the sign-up schemas), `acceptInvitationSchema` (its `home_group_name` gives the same "Enter 2 to 200 characters." as `org_name` did), and `personLoginSchema` (instead of `loginSchema`, without `user_type`).
   - **Keep:** `setProfile` and `term` (`terminology/terms.ts`) are used by the app inside their own file (`loadTerminology()` and `applyTerms()`), and `clearFlash` (`shared/flash.ts`) is a deliberate test helper called by `setupTests.ts`. `Voucher` (`api/types.ts`) is used by live types. `Me` is still reached through `AnyMe` and is left to S104, which removes the older account types.
4. **Unused CSS classes (13) are removed from the stylesheets:**
   - The old sidebar layout: `sidebar`, `sidebar-head`, `sidebar-close`, `shell-body`, `nav-list`, `nav-link`.
   - The others: `choice-grid`, `segmented`, `role-badge`, `result-contact`, `result-rate`, `tnum`, `txt`.
5. **Optional tidy-up:** drop `export` from the 20 names used only inside their own file. No other file, test or not, imports them: `Period` (`api/freelancer.ts`); `HandoverBody`, `GroupInvitationRow` (`api/person.ts`); `RatingBody` (`api/providers.ts`); `ReportCell`, `ChainLink` (`api/types.ts`); `notificationText` (`Notifications.tsx`); `vouchLinkUrl` (`VouchShare.tsx`); `joinUrl` (`GroupInvitations.tsx`); `inviteUrl` (`Churches.tsx`); `LIVE_DELAY_MS` (`FilterForm.tsx`); `prefersDialler` (`RevealMobile.tsx`); `FilterChip` (`activeFilters.ts`); `ReportTable`, `MAX_WINDOW_DAYS` (`ReportCard.tsx`); `MIN_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH`, `ValidationResult` (`validation.ts`); `useMedia` (`useWide.ts`); `DEFAULT_PROFILE` (`terms.ts`).
6. **Nothing a person sees changes.**

### How the list was verified (2026-11-27, on `main`)

In a throwaway copy of `frontend/`, everything in criteria 1 to 5 was removed and the tests were moved as in criterion 3. Then `tsc --noEmit`, `eslint .` and all 564 unit tests passed. Because `t()` accepts only known keys (`StringKey`), the type check proves that no fixed-text use of a removed key is left.

The ways around the compiler were checked by hand:
- **Computed keys:** every `t()` call with a computed key, and the one cast (`issue.message as StringKey`, whose sources are the validation messages in `validation.ts`).
- **Runtime-built classes:** every `className` built at runtime. Only `alert-${kind}` and `badge-${tone}` are, and they cannot produce a removed class.
- **The rest of the repository:** a search outside `frontend/src`. The only hits are the phone app's own copy of four keys in `mobile/lib/core/strings/strings_en.dart` (not shared with the web), and `version.txt`, which is a file name, not the class `txt`.

### Repositories affected:

Frontend: Yes

Backend: No

### Scope

Removal only, no new behaviour. It can be done before or after S104. Whichever comes second skips anything the first already removed. Do not perform any git push commands.

### Test Criteria

- `npm run typecheck`, `npm run lint`, `npm test` and the Playwright tests (`npm run e2e`) pass. The string keys are typed, so the type check fails if any removed key is still used.
- The light and dark themes look the same before and after on the main pages: the menu bar, search, the leader's pages and the owner's pages.

### Definition of Done

The test suite passes, and re-running the scan finds none of the items above.
