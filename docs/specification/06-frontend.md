# 06 Frontend

Decision record: [ADR-0005](../adr/0005-react-typescript-frontend.md). One React app, role-based portals sharing components. API access only through the generated client.

## Portals and pages

### Public
Landing, login, register (choose user type), forgot and reset password.

### Freelancer portal
Dashboard; profile; rate and currency; labels (skills with levels, languages, timings, nativity); unavailability calendar; my ratings; my organisation vouches.

### Work host portal
Dashboard; profile and available days; freelancer search with filters and sorting; freelancer detail; rate a freelancer; my ratings given.

### Organisation portal
Dashboard; profile; vouched freelancers (add, revoke, status); organisation reports.

### Admin portal
Report pages (RP-01 to RP-07), scheduled-run history and downloads, label management.

## UI requirements

- Responsive, usable on a phone browser.
- Accessible: keyboard navigation, labels on inputs, sufficient contrast (WCAG 2.1 AA target).
- Form validation with zod mirroring API rules; show API error messages clearly.
- Access token kept in memory; silent refresh using the refresh token; log out on refresh failure.
- Loading, empty and error states for every list and page.
- Strings kept in a translation file so more languages can be added (Q9).
