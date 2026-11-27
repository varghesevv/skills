### Background

There is no initial config file that is read on startup, to minimally populate the application on startup.

### Feature Criteria

1. The application must boot up by reading this minimal config in initial.json. 

initial.json

1. There should also be a schema.json file (not provided), containing the valid data structures allowed in initial.json. The schema.json will be derived from the existing codebase and the demo-logins.csv (attached)

demo-logins.csv

### Repositories affected:

Frontend: Yes

Backend: Yes

### Scope

Do not perform any git push commands.

### Test Criteria

Create appropriate tests for this feature.

### Definition of Done

The test suite passes

### Agreed design (2026-11-27)

The repository is public, so `initial.json` is committed and holds **no secrets and no real personal details**.

1. **`backend/initial.json` (committed)** holds only the structure: the OWNER, each church ("organisation") with its ADMIN, each home group with its leader (VERIFIER), with placeholder names and emails, and `verification_conditions`: the default wording of the conditions a verifier ticks before Admit (see `docs/verification.md`, "What verified means"). Searchers and providers are never in it: they join through the app with their vouches. `backend/schema.json` describes the format.
2. **First start (empty database):** the server creates the tables, then the structure, as one operator change. Nobody can sign in yet. The server writes a **one-time setup code** to its log.
3. **Setup page**, opened with that code: the OWNER enters their own name, email, mobile and password; the name, email and mobile of every ADMIN and leader; and confirms or edits the wording of the conditions. The code then stops working, and the conditions are fixed from then on.
4. **ADMINs and leaders** each get a **set-your-password link** (in the server log until email exists) and choose their own password. Nobody knows another person's password.
5. **Later starts** check only the structure (church and home group names, and who holds which role) against the database, and refuse to start when they differ. People's details are never compared.

Frontend: the setup page and the set-your-password page (web; the phone app needs no setup screen).

### What is built so far, and what changes

Built on this branch: reading `initial.json` at start-up, `schema.json`, creating the tables on an empty database, the start-up check, and a forced password change for temporary passwords from the file. To change for the agreed design: no passwords or real details in the file (placeholders instead), `verification_conditions` in the file and stored, the setup code and page, set-your-password links for ADMINs and leaders (replacing the forced change of a temporary password), and a structure-only start-up check.
