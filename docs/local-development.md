# Run Skills on your own computer

A step-by-step guide for people who are new to this kind of project. You do not need to know FastAPI, React or Docker beforehand. Follow the steps in order; each one says what you should see, so you know when it worked.

**What you will have at the end:** the whole application running on your laptop (database, API, background worker and web site), with fake demo people to log in as, and the tools to change code and see the result immediately.

**How long:** about 30 minutes, most of it downloads on the first run.

Contents

1. [How the pieces fit together](#1-how-the-pieces-fit-together)
2. [Install the tools](#2-install-the-tools)
3. [Get the code](#3-get-the-code)
4. [Start the application](#4-start-the-application)
5. [Create demo data and log in](#5-create-demo-data-and-log-in)
6. [Everyday commands](#6-everyday-commands)
7. [Change code and see it live](#7-change-code-and-see-it-live)
8. [Run the checks and tests](#8-run-the-checks-and-tests)
9. [Work with the database](#9-work-with-the-database)
10. [Reports](#10-reports)
11. [When something goes wrong](#11-when-something-goes-wrong)
12. [Words you will meet](#12-words-you-will-meet)
13. [Where to go next](#13-where-to-go-next)

---

## 1. How the pieces fit together

```
 your browser                                   your computer (inside Docker)
 ┌───────────────┐   http://localhost:5173    ┌─────────────┐
 │  the web site │ ─────────────────────────► │  web        │  React app, served by Vite
 └───────────────┘                            └──────┬──────┘
                                                     │ /api/...  (forwarded)
                                                     ▼
                       http://localhost:8000  ┌─────────────┐        ┌────────────┐
                       (API docs at /docs)    │  api        │ ─────► │  db        │  PostgreSQL
                                              │  FastAPI    │        │  (data)    │
                                              └─────────────┘        └─────▲──────┘
                                              ┌─────────────┐              │
                                              │  worker     │ ─────────────┘
                                              │  scheduled  │  builds the scheduled reports
                                              └─────────────┘
```

| Part | What it is | Where the code is |
|---|---|---|
| **web** | The site you click around in. Four areas (portals): freelancer, work host, organisation, admin. | `frontend/` |
| **api** | The server that holds the rules. The web site (and later a mobile app) only talk to it over HTTP. | `backend/` |
| **worker** | A small program that runs reports on a schedule (for example every morning). | `backend/app/worker` |
| **db** | PostgreSQL, the only place data is stored. | started from `docker-compose.yml` |

**Docker** runs all four parts for you in isolated boxes called containers, so you do not install PostgreSQL, Python or Node on your computer. The file `docker-compose.yml` describes the boxes; the command `docker compose` starts them.

---

## 2. Install the tools

You need **three** things. A fourth group is optional.

| Tool | Why | Required? |
|---|---|---|
| Git | download and track the code | yes |
| Docker (with Docker Compose) | runs the whole application | yes |
| `make` and `openssl` | `make env` creates your private settings file | yes |
| Node.js 22 and Python 3.12 with `uv` | run tests and checks outside Docker | optional (needed for section 8) |

### macOS

1. Install the Apple command line tools (this gives you `git` and `make`). In Terminal:
   ```bash
   xcode-select --install
   ```
2. Install **Docker Desktop for Mac** from <https://www.docker.com/products/docker-desktop/>, open it once and wait until it says Docker is running.
3. `openssl` is already installed.

### Windows

Use **WSL 2** (a real Linux inside Windows). Everything below is then the same as on Linux.

1. Open PowerShell as administrator and run `wsl --install -d Ubuntu`, then restart the computer and finish creating your Ubuntu user.
2. Install **Docker Desktop for Windows** and, in Settings → Resources → WSL integration, switch on Ubuntu.
3. Open the **Ubuntu** app and run:
   ```bash
   sudo apt update && sudo apt install -y git make openssl curl
   ```
4. Always work inside your Ubuntu home folder (`cd ~`), not under `/mnt/c`. It is much faster and avoids file permission problems.

### Linux (Ubuntu or Debian)

```bash
sudo apt update && sudo apt install -y git make openssl curl
```

Install Docker Engine and the Compose plugin by following <https://docs.docker.com/engine/install/ubuntu/>, then let your user run Docker without `sudo` and log out and in again:

```bash
sudo usermod -aG docker "$USER"
```

### Check your tools

Run each line. You should see a version number, not an error (your numbers will differ):

```bash
git --version
docker --version
docker compose version
make --version
openssl version
docker run --rm hello-world       # prints "Hello from Docker!"
```

### Optional: Node.js and Python tools (for tests and checks)

You can skip this until section 8.

- **Node.js 22 or newer.** Easiest is [nvm](https://github.com/nvm-sh/nvm): `nvm install 22`. Check with `node --version`.
- **uv** (installs Python 3.12 and the backend libraries for you):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS, Linux, WSL
  ```
  Open a new terminal, then `uv --version`.

---

## 3. Get the code

```bash
git clone https://github.com/varghesevv/skills.git
cd skills
```

A quick tour of the folders:

| Folder | Contents |
|---|---|
| `backend/` | The API: `app/` (code), `migrations/` (database changes), `tests/` |
| `frontend/` | The web site: `src/` (code), `e2e/` (browser layout checks) |
| `docs/` | The specification (what we build) and ADRs (why we chose things) |
| `infra/` | Servers on AWS and deployment. You can ignore it for local work. |
| `scripts/` | Helper scripts such as the secret scanner |
| `docker-compose.yml` | Describes the four local containers |
| `Makefile` | Short commands, listed with `make help` |

---

## 4. Start the application

### 4.1 Create your private settings file

```bash
make env
```

This creates a file called `.env` from `.env.example`. It fills in **random** passwords for the database, for login tokens and for the demo users. You will see lines like `Set POSTGRES_PASSWORD (generated, not shown)`. The values are never printed.

Two important rules:

- `.env` is private to your computer and is ignored by Git. **Never commit it, never paste its contents into chat, issues or pull requests.** Secrets always come from environment variables, never from files in Git.
- Running `make env` again is safe; it never changes values that already exist.

The settings you might care about:

| Setting | Meaning | Default |
|---|---|---|
| `WEB_PORT` | web site port on your computer | `5173` |
| `API_PORT` | API port | `8000` |
| `DB_PORT` | database port | `5432` |
| `ENVIRONMENT` | `local` means relaxed rules; `demo`/`prod` demand strong secrets | `local` |

If another program already uses one of those ports, change the number in `.env` (see section 11).

### 4.2 Start everything

```bash
docker compose up --build
```

The first run downloads images and installs libraries, so give it **5 to 10 minutes**. Later runs take seconds. You will see a lot of coloured log lines from four services. It is ready when you see lines like:

```
api-1     | INFO:     Application startup complete.
web-1     |   VITE v... ready in ... ms
web-1     |   ➜  Local:   http://localhost:5173/
```

This terminal now belongs to the application. Leave it open; press `Ctrl+C` to stop it. (To run it in the background instead, use `make up`, and `make logs` to watch.)

On the first start the API also creates all database tables and the starting labels (skills, languages, timings, nativity, skill levels) by itself. You do not run any database command.

### 4.3 Check that it works

Open these in your browser:

| Address | What you should see |
|---|---|
| <http://localhost:5173> | The Skills web site (landing page, log in, register) |
| <http://localhost:8000/docs> | Interactive API documentation. You can try every endpoint here. |
| <http://localhost:8000/health> | `{"status":"ok"}` |

Or from a second terminal:

```bash
curl http://localhost:8000/health
docker compose ps                       # all four services should be "running" or "healthy"
```

If a page does not load, jump to [section 11](#11-when-something-goes-wrong).

---

## 5. Create demo data and log in

The site starts empty. Open a **second terminal**, `cd skills`, and create people to log in as. Run these while the application is running.

The demo data commands need the demo password from `.env`. The one-liner below reads it for that single command without printing it.

### 5.1 A few ready-made accounts (quickest)

```bash
docker compose exec \
  -e DEMO_USER_PASSWORD="$(sed -n 's/^DEMO_USER_PASSWORD=//p' .env)" \
  api python -m app.cli seed-demo
```

(Type it as one line if your terminal does not accept the line breaks.) It prints `Demo users created: 8`. The accounts are:

| Account type | Email |
|---|---|
| admin | `admin@example.com` |
| freelancer | `anita.plumber@example.com`, `joseph.electrician@example.com`, `maria.carer@example.com` |
| work host | `host.one@example.com`, `host.two@example.com` |
| organisation | `org.approved@example.com` (can log in), `org.pending@example.com` (waits for admin approval) |

Password for all of them: the value of `DEMO_USER_PASSWORD` in your `.env`. To read it on your own computer only:

```bash
sed -n 's/^DEMO_USER_PASSWORD=//p' .env
```

### 5.2 A large realistic data set (about 260 people)

This creates 10 organisations (8 approved, 1 pending, 1 rejected), 50 work hosts and 200 freelancers with varied skills, skill levels, timings, languages and nativity, plus vouches, ratings and planned time off. It writes a login list as a CSV file:

```bash
docker compose exec -T \
  -e DEMO_USER_PASSWORD="$(sed -n 's/^DEMO_USER_PASSWORD=//p' .env)" \
  api python -m app.cli generate-demo-data --csv - --reset > demo-logins.csv
```

Check it: `wc -l demo-logins.csv` should say `261` (260 accounts plus a header).

`demo-logins.csv` has the columns `user_type, email, password, name, status`. **It contains the demo password.** Git ignores files with this name, but never share it. `--reset` removes earlier generated people first, so you can run the command again any time for a fresh set. Open the CSV in a spreadsheet and pick any row to log in as that person.

### 5.3 Create your own admin account

```bash
docker compose exec api python -m app.cli create-admin --email you@example.com --mobile +971500000000
```

It asks for a password twice (you will not see what you type). In `local` the password must be at least 10 characters.

### 5.4 Log in

1. Open <http://localhost:5173>. There are three login pages:
   - **Log in** (`/login`) for freelancers and work hosts. Switch between the two with the links **Freelancer** and **Work host** at the top of the form.
   - **Organisation log in** (`/login/organisation`), only for organisations. Open it by address; the main login page does not link to it.
   - **Admin log in** (`/login/admin`), only for administrators. Open it by address; no page links to it.
2. Enter the email and password of that kind of account. An account of another kind is rejected on the wrong page.
3. Try each type to see its area:
   - **Freelancer**: profile, skills and labels, availability calendar, vouches, ratings.
   - **Work host**: search freelancers, rate them.
   - **Organisation**: vouch for freelancers. A new organisation cannot log in until an admin approves it.
   - **Admin**: approve organisations, manage labels, run and download reports, schedules.

"Forgot password" does not send email locally. The reset link is written to the API log:

```bash
docker compose logs api | grep -i reset
```

---

## 6. Everyday commands

Run them from the `skills` folder.

| I want to... | Command |
|---|---|
| Start everything in the background | `make up` |
| Start in the foreground and watch the logs | `docker compose up` |
| Stop everything, **keep** the data | `make down` |
| See what is running | `make ps` |
| Follow the logs of all parts | `make logs` (stop watching with `Ctrl+C`) |
| Follow one part | `docker compose logs -f api` (or `web`, `worker`, `db`) |
| Restart one part | `docker compose restart api` |
| Open a shell inside the API container | `docker compose exec api sh` |
| **Delete all data** and start clean | `make reset-db`, then `make up` and redo section 5 |
| List every shortcut | `make help` |

Ignore the targets starting with `pi-` and `sync-`. They are for one developer's Raspberry Pi setup.

---

## 7. Change code and see it live

Both the API and the web site reload by themselves when you save a file. You do not rebuild or restart.

**Try the frontend.** Open `frontend/src/i18n/index.ts`, change a piece of text (all visible text lives there), save, and look at the browser: it updates within a second.

**Try the backend.** Open `backend/app/api/health.py`, change `"ok"` to `"fine"`, save, and open <http://localhost:8000/health>. Change it back afterwards.

Where things live:

| I want to change... | Look in |
|---|---|
| a page or a form | `frontend/src/pages/`, `frontend/src/portals/<portal>/` |
| text on screen | `frontend/src/i18n/index.ts` |
| colours, spacing, layout | `frontend/src/styles/global.css` |
| an API endpoint | `backend/app/api/v1/` |
| a business rule | `backend/app/services/` |
| a database table | `backend/app/models/` (and add a migration, see section 9) |
| a report | `backend/app/reports/` |

Read `CONTRIBUTING.md` before you open a pull request: branch names, commit messages, the definition of done, and the strict rule about secrets.

---

## 8. Run the checks and tests

The checks are the same ones the project runs automatically on every pull request. Run them before you push. They need the optional tools from section 2 (Node 22, `uv`).

### Frontend

```bash
cd frontend
npm install                 # once, and after dependencies change
npm run lint                # code style problems
npm run format:check        # formatting (fix with: npm run format)
npm run typecheck           # TypeScript errors
npm test                    # unit tests
```

Or all four at once from the repository root: `make fe-install` then `make fe-check`.

**Layout checks in a real browser** (phone, tablet and desktop sizes):

```bash
cd frontend
npx playwright install chromium     # once, downloads a test browser
npm run e2e
```

Screenshots of every page are kept in `frontend/playwright-report` and `frontend/test-results`.

### Backend

The backend tests use a real PostgreSQL database, which the project starts for you:

```bash
make be-install             # uv sync: installs Python libraries
make be-test                # starts the database, then runs pytest
make be-check               # lint, format check and type check
make openapi                # rewrite docs/openapi.json after you change an endpoint or a schema
```

Running only some tests:

```bash
set -a; . ./.env; set +a
export DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$DB_PORT/$POSTGRES_DB"
cd backend
uv run pytest tests/test_health.py -v
uv run pytest -k "ratings" -v
```

The tests create their own databases (`skills_test` and others) and never touch the data you created in section 5.

### Secrets check

```bash
make check-secrets          # looks for passwords or keys committed by accident
make install-hooks          # runs that check automatically before every commit
```

---

## 9. Work with the database

**Look inside it** (read before you write):

```bash
docker compose exec db psql -U skills -d skills
```

Useful commands at the `skills=#` prompt: `\dt` lists tables, `\d freelancers` describes one, `SELECT label_type, label_name FROM labels ORDER BY 1, 2;` shows the labels, `\q` quits.

**Changing the data model.** Tables are defined as Python classes in `backend/app/models/`. A change needs a *migration*, a small script that upgrades the database:

```bash
set -a; . ./.env; set +a
export DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$DB_PORT/$POSTGRES_DB"
cd backend
uv run alembic revision --autogenerate -m "describe the change"
```

Open the new file in `backend/migrations/versions/` and read it. Automatic generation can miss triggers and constraints. Apply it with `docker compose restart api` (the API upgrades on start) or `make be-migrate`. Never edit a migration that is already merged; add a new one.

**Start over:** `make reset-db` deletes the database volume. All local data is lost, which is exactly what you want when experimenting.

---

## 10. Reports

Admins create and download reports in the web site (Admin → Reports, Report history and Schedules). From the command line:

```bash
docker compose exec api python -m app.reports list
docker compose exec api python -m app.reports run users_registered_daily --from 2026-10-20 --to 2026-10-20
```

Files are written to the reports folder inside the container. The `worker` container runs the scheduled reports (daily, weekly, monthly); `docker compose logs -f worker` shows when it runs. Only one worker should ever run.

---

## 11. When something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| `Cannot connect to the Docker daemon` | Docker is not running. Open Docker Desktop and wait for "running". On Linux: `sudo systemctl start docker`. |
| `permission denied ... docker.sock` (Linux) | Run `sudo usermod -aG docker "$USER"`, then log out and in. |
| `Run make env to create or complete .env` | You skipped section 4.1. Run `make env`. |
| `port is already allocated` / `address already in use` | Another program uses 5173, 8000 or 5432 (often a local PostgreSQL). Stop it, or change `WEB_PORT`, `API_PORT` or `DB_PORT` in `.env` and run `docker compose up` again. Then use the new port in your browser. |
| Browser shows nothing at port 5173 | The web container is still running `npm install`. Watch `docker compose logs -f web` until it says `ready`. |
| `DEMO_USER_PASSWORD is not set` | The value is empty in `.env`. Run `make env` (it fills empty secrets), then retry. Remember the `-e DEMO_USER_PASSWORD=...` part of the command. |
| `In demo, DEMO_USER_PASSWORD must be strong...` | `ENVIRONMENT` in `.env` is `demo`. Local development uses `ENVIRONMENT=local`. |
| `An admin with this email already exists` | It is already created. Log in, or use another email. |
| Login says the account is not approved | An organisation needs admin approval. Log in as admin → Organisations → approve it. |
| Error "Too many failed attempts" (HTTP 429) | Five wrong passwords for the same email lock that login for 15 minutes, by design. Wait, or use another account. |
| `demo-logins.csv` is empty | The command failed before writing. Run it without `> demo-logins.csv` to read the error message. |
| Changes in `backend/` are not picked up | Check `docker compose logs api` for a syntax error. The API reloads only when the file is valid. |
| Tests say database not reachable | Run `make be-test`, which starts the database first, or `docker compose up -d --wait db`. |
| Everything is broken and you want a clean slate | `docker compose down -v` (deletes the database), then `docker compose up --build`. |
| `uv: command not found` / `node: command not found` | Open a new terminal after installing, or install the optional tools from section 2. |
| Windows: very slow or odd file errors | The project is under `/mnt/c`. Move it into your Ubuntu home folder (`~`). |

Still stuck? Copy the error text (never the contents of `.env`), look in `docker compose logs`, and ask with those details.

---

## 12. Words you will meet

| Word | Meaning here |
|---|---|
| **API / REST** | The server's front door. The site sends it requests such as "list freelancers" over HTTP and gets JSON back. |
| **Backend / frontend** | The server side (`backend/`) and the browser side (`frontend/`). |
| **Container / image** | A packaged, isolated mini-computer that runs one part of the application. |
| **Docker Compose** | The tool that starts all containers together from `docker-compose.yml`. |
| **Migration** | A versioned script that changes the database structure (Alembic). |
| **Seed** | Creating starting or demo data. |
| **Label** | A choice such as a skill, language, timing, nativity or skill level that describes a freelancer. |
| **Vouch** | An approved organisation saying "we stand behind this freelancer". |
| **Portal** | One role's area of the site (freelancer, work host, organisation, admin). |
| **Token** | The proof of login the site sends with every request. The API is stateless: no server-side sessions. |
| **Worker** | A background program that does scheduled jobs, here the reports. |
| **ADR** | Architecture Decision Record: a short note explaining why a technical choice was made. |

---

## 13. Where to go next

1. [Specification](specification/README.md): what the product must do. Start with `01-overview.md` and `02-functional-requirements.md`.
2. [Architecture decisions](adr/README.md): why PostgreSQL only, why token login, and so on.
3. [CONTRIBUTING.md](../CONTRIBUTING.md): how to work with the team.
4. [Backend notes](../backend/README.md) and [frontend notes](../frontend/README.md): details for each side.
5. [Open questions](open-questions.md): decisions still waiting on the product owner. Do not guess these.

A good first exercise: pick one small label or text change, run the frontend checks, push a branch and open a pull request. That walks you through the whole workflow.
