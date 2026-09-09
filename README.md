# SPI Staff Outline System — backend

Everything here now runs as **one Flask app**, built with the
app-factory + Blueprint pattern so each group keeps owning its own
file(s) instead of everyone editing one giant app.py.

## Configuration (do this first)

Every credential (Azure, mail, database) is read from environment
variables — nothing is ever hardcoded in source. Locally, the easiest
way to set them is a `.env` file:

```
cp .env.example .env
```

Then open `.env` and fill in real values. It loads automatically the
moment you run the app (see `load_dotenv()` at the top of
`SPIStaffOutlineSystem.py`) — no need to `export` anything by hand
every session.

**`.env` is git-ignored on purpose** (see `.gitignore`) — it holds
real secrets and must never be committed. `.env.example` (placeholders
only) is what's safe to commit and share with the team.

**When this gets actually deployed somewhere** (Render, Railway, a
real server, etc.): don't upload your `.env` file to the host. Almost
every hosting platform has its own place to set environment variables
(a dashboard, a secrets manager, a CLI command) — put the same
key/value pairs there instead. The app doesn't care where the
variables come from, `.env` or the platform, `os.environ.get(...)`
reads them the same way either way. If a teammate needs the real
values to deploy their own copy, send them directly (a password
manager's shared vault, not chat/email) — never by putting them in a
file that goes in git.

Install dependencies with:
```
pip install -r requirements.txt
```

## Entry point

Run:

```
python SPIStaffOutlineSystem.py
```

Then visit `http://localhost:5000/`.

`SPIStaffOutlineSystem.py` builds the app (`create_app()`) and
registers each group's Blueprint. Nothing else has an
`app.run()`/server-start of its own anymore.

## Project layout

Files are now grouped by which group owns them, instead of all sitting
flat in one folder:

```
spi_backend/
├── SPIStaffOutlineSystem.py   <- run this one
├── frontend_server.py          (root-level — not owned by a group)
├── auth/
│   ├── __init__.py
│   ├── login.py
│   └── server.py                (auth_bp)
├── email_approval/
│   ├── __init__.py
│   ├── app.py                   (email_bp)
│   └── email_service.py
├── dashboard/
│   ├── __init__.py
│   └── dashboard.py              (dashboard_bp)
├── editing/
│   ├── __init__.py
│   ├── editing.py
│   ├── routes.py                (editing_bp)
│   └── CreateNewDoc.py
├── shared/                      <- used by every group, owned by none
│   ├── __init__.py
│   ├── retrieve_database.py
│   └── error.py
└── frontend/                    <- static files, not Python
    ├── index_1.html
    ├── script.js
    ├── unit.js
    └── styles.css
```

Each backend folder (except `frontend/`, which isn't Python) has an
empty `__init__.py` so it's a real package — that's what makes
`from auth.login import UserLogin`-style imports work. Imports between
folders are absolute, not relative, which means **this only works if
you run `python SPIStaffOutlineSystem.py` from inside the
`spi_backend/` folder itself** — not from somewhere else, and not by
importing it as a module from another project.

| File | Owns | Notes |
|---|---|---|
| `SPIStaffOutlineSystem.py` | App factory / entry point | The only file with `app.run()` |
| `frontend_server.py` | `frontend_bp` — `/` and static files | Serves `frontend/index_1.html`, `script.js`, `unit.js`, `styles.css` from the same origin as the API, which is what lets the Microsoft login session cookie work without CORS. Renamed from `frontend.py` so it doesn't share a name with the `frontend/` folder it serves |
| `auth/login.py` | Microsoft OAuth logic | Extracts a display `name` from the token claims, alongside email/roles. `UserRole`/`UserSignOut` no longer inherit MSAL setup they didn't need (see Login/session section below) |
| `auth/server.py` | `auth_bp` — `/login`, `/auth/callback`, `/logout`, `/whoami`, `/api/session`, `/dev-login/<role>`, `/api/dev-mode` | Converted from `http.server` to Flask. `/dev-login/<role>` is a Microsoft-bypass for local testing — only works when `DEV_MODE` is set, see below |
| `email_approval/app.py` | `email_bp` — `/test-create`, `/approve/<token>`, `/reject/<token>`, `/logs`, `/api/change-requests` | No longer owns a DB or the `/` route (that's `frontend_server.py` now) |
| `email_approval/email_service.py` | Sends the approval email | Logs through `Retrieve_Database` instead of its own DB |
| `shared/retrieve_database.py` | Shared data-access layer | **Real MySQL** — see the setup instructions at the top of the file (`pip install mysql-connector-python` + `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` env vars). Matches the schema in `db_group_guide.md` |
| `editing/editing.py` | `CreateNewDoc`, `SaveDoc`, `DeleteDoc`, `ApprovalReq`, `PrintPDF` | `ApprovalReq` is a thin adapter over `retrieve_database.py` + `email_service.py`. `SaveDoc` really writes to `unit_outlines` + `history_log` now: `run()` still requires an approved `ApprovalReq`, `run_direct()` skips it (what the Save button uses) |
| `editing/routes.py` | `editing_bp` — `GET`/`POST /editing/api/outlines/<unit_code>` | Load/save a unit outline. This is what the Save Outline Changes button calls |
| `editing/CreateNewDoc.py` | `UnitOutline` — the python-docx builder | Unchanged |
| `dashboard/dashboard.py` | `dashboard_bp` — `/dashboard/api/courses` (GET/POST/PUT/DELETE) | Course list is real — synced from the `courses`/`staff_course_access` tables. Write operations require the admin role, checked server-side. `DisplayUserCourse`/`CourseFilter` are still unbuilt stubs |
| `shared/error.py` | Error handling | Still a stub |
| `frontend/` | `index_1.html`, `script.js`, `unit.js`, `styles.css` | The real frontend. Login screen links to `/login` instead of a local password form; `checkAuthSession()` calls `/api/session` instead of trusting `localStorage` alone |

## Known gaps (not fixed here, flagged so nothing gets lost)

- **`retrieve_database.py` is a mock.** Data doesn't survive a restart.
  The DB group needs to swap the internals for real storage, keeping
  the same method names.
- **`retrieve_database.py` needs real MySQL credentials to run.** Set
  `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` before starting the app —
  see the setup comment at the top of the file. It fails fast with a
  clear error if any are missing.
- **`DeleteDoc` is still not wired up, and is blocked on the schema —
  not on effort.** `history_log.unit_outline_id` is a FOREIGN KEY to
  `unit_outlines(unit_outline_id)` with no `ON DELETE` rule, so MySQL
  refuses to delete an outline that has history rows AND refuses to
  insert a history row for an outline that's already gone. Either
  order fails, so "delete the outline and log the deletion" is
  currently impossible. Pick one fix first — `ON DELETE CASCADE`,
  `ON DELETE SET NULL`, or a soft-delete flag (recommended for an
  approvals-based system) — then `delete_from_database()` becomes two
  lines. See the docstring on that method for the details.

## Buttons wired to the real backend so far

- **Login / logout** — see the "Login/session integration" section below.
- **Dashboard course list** — loads real courses via
  `GET /dashboard/api/courses` on every dashboard load
  (`syncCoursesFromBackend()` in script.js).
- **Add Course / Edit Course / Delete Course** (Admin only) — call
  `POST` / `PUT` / `DELETE /dashboard/api/courses` respectively, then
  re-sync. Role is checked server-side (`_require_admin()` in
  dashboard.py), not just hidden client-side.
- **"Request a Change"** — this now IS the real email approval system
  (confirmed: it's not a separate feature). Submitting the form calls
  `POST /api/change-requests` (app.py), which creates a real approval
  record and sends a real email — including the requested changes
  themselves, not just the unit code (see `send_approval_email`'s new
  `change_summary` param). The Change Requests screen polls
  `GET /api/change-requests/<token>` to reflect the approver's actual
  Approve/Reject click from the email. The old "Mark Approved/Rejected"
  buttons only still appear for requests created before this was wired
  up (no token) — see `resolveChangeRequest()`'s comment. Requires an
  "approver's email" (new field on the form) since there's no staff
  directory to pick one from automatically.

### Save Outline Changes → the `unit_outlines` table

The Save button on the unit outline screen now writes the outline into
the database instead of only into the browser.

- `POST /editing/api/outlines/<unit_code>` — saves. First save for a
  unit **inserts** a row at version 1; every save after that **updates
  that same row** and bumps `version`. Each save also appends a
  `history_log` row (`action='saved'`, who, when, which version).
- `GET /editing/api/outlines/<unit_code>` — loads it back, so opening a
  unit shows what's in the database rather than what happens to be in
  that particular browser. `404` means "never saved" (a normal answer
  for a new course, not an error) and the form shows the blank template.

**The content shape question is settled.** `unit_outlines.content`
holds a JSON object of the Unit Outline form's field ids →their values
— exactly what `collectOutlineData()` builds in `script.js`. JSON, not
the `.docx` bytes, because the frontend has to read it straight back
into the form; building the `.docx` stays `CreateNewDoc.py`'s job, done
on demand at export time from these same fields.

**No approval gate on this button, deliberately.** It calls
`SaveDoc.run_direct()`, not `SaveDoc.run()`. Saving here is an
authorised editor saving their own work in a unit they already have
access to; the approval workflow belongs to the separate "Request a
Change" feature, where someone *without* edit rights asks for a change.

**Permissions are enforced server-side.** Admins can save any unit;
everyone else can only save units they hold in `staff_course_access`
(`_may_edit()` in `editing/routes.py`). `script.js`'s field-locking is
cosmetic only.

**If the database write fails**, the form still saves locally and the
toast says so explicitly ("Saved in this browser, but NOT to the
database — <reason>") rather than claiming success. The user's typing
is never lost to a failed request.

### Request a Change → real email (and honest failures)

The modal no longer grows past the screen. `.modal` is capped at
`calc(100vh - 40px)` and is a flex column: the heading and the
Cancel/Submit row stay put, and the middle (`.modal-body`) scrolls. It
used to have no height limit at all, so queueing enough changes pushed
the buttons below the bottom of the window with no way to reach them —
the backdrop is `position:fixed`, so scrolling the page didn't help.
Also raised `.modal-backdrop` to `z-index:150`: it was `100`, the same
as the sticky `nav`, and since the nav comes later in the HTML it won
the tie and painted over the modal's heading.

**Email failures are now reported instead of hidden.** `send_email()`
used to catch every exception, print it to the terminal, and return
`False` — and `send_approval_email()` ignored that return value. A
failed send was indistinguishable from a successful one: a change
request was created, the user was told it was submitted, and no email
ever arrived. Now `send_email()` raises `EmailSendError`, the route
returns `502` with the real reason, and the frontend shows it in a red
toast that stays up for 9 seconds (long enough to read a sentence).
Specific improvements:

- Missing `MAIL_USERNAME`/`MAIL_PASSWORD` is detected before connecting,
  so you get "the mail account is not configured" rather than an SMTP
  authentication error that reads like a wrong password. **For Gmail,
  `MAIL_PASSWORD` must be a 16-character App Password**, not the normal
  account password.
- The approver address is validated on both sides. The input is
  `type="email"` but isn't inside a `<form>`, so nothing was checking
  it — `test` was accepted and handed to the mail server.
- Failed sends are written to the email log with `status="Failed: ..."`,
  so `/logs` shows what was attempted and didn't arrive.
- A database failure while logging a *successful* send no longer reports
  the email as failed.
- Change text is HTML-escaped before going into the email body.
- The Approve/Reject links use `APP_BASE_URL` (set it in `.env` once
  hosted); they were hardcoded to `127.0.0.1:5000`, so they only worked
  for someone sitting at the machine running the server.

### The dashboard course list is the database only

`defaultCourses` is gone. `getCoursesStore()` used to seed three
hardcoded sample courses (CS101 / IT201 / AI301) whenever localStorage
was empty, which meant a failed database call rendered a perfectly
normal-looking dashboard — and then saved that sample data into
localStorage as if it were real. That's why those three kept appearing
when nothing was reaching MySQL. Now an empty cache is just empty, and
`renderCourses()` tells the two situations apart: "No courses yet"
versus "Could not load courses from the database", the second naming
the `DB_*` variables to check.

The **"Units from Python backend"** table is deleted, along with
`loadUnitsFromBackend()`, `renderBackendUnits()`, `BACKEND_URL` and the
`unit.js` script tag. It was a teaching demo calling `/api/units`, a
route this app has never had, so it only ever displayed a red error —
and it duplicated the My Courses cards directly above it.

### Export All → a ZIP with one JSON per course

`GET /dashboard/api/courses/export` (dashboard.py) builds a ZIP holding
one file per course — `ICT101.json`, `ICT202.json`, … — each including
that unit's outline content from `unit_outlines` when it has been saved.
It used to be a single `spi-courses.json` with everything in one array,
built from the localStorage cache rather than the database.

A ZIP rather than one download per course because a page cannot start
several downloads on its own: Chrome interrupts with a "Download
multiple files?" prompt and other browsers drop all but the first. One
ZIP always arrives, and extracting it gives you the separate files.
Filenames are sanitised (a course code is free text in the database, so
it could otherwise contain path separators) and de-duplicated.

### Import JSON → creates real courses

`importCourseData()` now POSTs each course to
`/dashboard/api/courses`, so imports persist. Previously it only wrote
to localStorage, and since the dashboard re-syncs from the database on
every load, anything imported vanished on the next refresh — it looked
like the button did nothing.

Error reporting was the other half of the problem: every failure said
"Import failed: invalid JSON file" regardless of cause. Now the real
`SyntaxError` is passed through, so a stray character at the end of a
file reads as *"Unexpected non-whitespace character after JSON at
position 37 (line 3 column 2)"* — which tells you where to look.
Entries that aren't course data are counted and reported separately,
duplicates come back as `409 A course with code 'X' already exists`
instead of a raw HTML 500 page, and the file input is reset so the same
file can be chosen twice in a row.

Related crash fixes in `dashboard.py`, all of which used to escape as
unhandled `IntegrityError`s and return HTML 500 pages the frontend
couldn't parse: duplicate course code on create/update (now `409`), and
deleting a course that still has rows in `staff_course_access` (now
`409` with an explanation).

## Still local-only / not wired (and why)

- **Staff management screen — removed.** Confirmed: identity and
  roles are Azure AD only, so there's no in-app equivalent needed.
  Deleted `staffScreen`, the `staffModal`, and every JS function that
  only existed to support them (`getStaffStore`, `setStaffStore`,
  `demoUsers`, `loadStaffScreen`, `renderStaffTable`,
  `openAddStaffModal`, `submitAddStaff`, `updateStaffRole`,
  `removeStaff`). `screenForRole()` now sends every role to the same
  dashboard. Also confirmed: **only 3 roles exist** (`admin`,
  `course_coord`, `unit_coord`) — `hr` was removed entirely, from
  `roleLabels`, the dev-login buttons, and `DEV_USERS` in
  `auth/server.py`. A few now-unused CSS classes (`.staff-role-select`
  etc.) were left in `styles.css` — harmless, just dead weight, not
  worth the risk of a broad CSS edit to chase down every one.
- **`PrintPDF.generate_pdf` raises `NotImplementedError`** — waiting on
  the PDF group's conversion function.
- **No routes call `CreateNewDoc`/`DeleteDoc` yet.** (`SaveDoc` now
  has one — see the Save Outline Changes section above.) If a save
  ever needs to wait on an approval, `editing/routes.py` should create
  an `ApprovalReq(mail)`, call
  `request_approval(unit_code, coordinator_email)`, and use
  `SaveDoc.run(...)` — which gates on `check_status()` — instead of
  `run_direct(...)`.
- **Bugs fixed along the way, worth knowing about:**
  - `dashboard.py`, `editing.py`, `error.py`, and the old
    `retrieve_database.py` all inherited from the *module*
    `SPIStaffOutlineSystem` instead of a class — invalid Python,
    would raise `TypeError` on run. Removed that inheritance
    entirely; nothing was actually relying on it since the base
    `__init__` was a no-op.
  - `editing.py`/`dashboard.py` used to `import Retrieve_Database`
    (capitalized, no `from`) when the file is `retrieve_database.py`
    — fixed to `from retrieve_database import Retrieve_Database`.
  - `dashboard.py`'s `class filter(Dashboard)` shadowed Python's
    builtin `filter()` — renamed to `CourseFilter`.
  - `editing.py`'s `PrintPDF` had two `def __init__` methods (the
    second silently overrode the first, breaking
    `PrintPDF(sheet=...)`) — removed the duplicate.
  - Gmail credentials were hardcoded in `app.py` — now read from
    `MAIL_USERNAME`/`MAIL_PASSWORD` environment variables.

## Login/session integration — what's done and what's still open

- **Dev login (bypass Microsoft entirely for now):** set
  `export DEV_MODE=1` before running the app, and the login screen
  shows 4 buttons — Administrator / Course Coordinator / Unit
  Coordinator — that log you in instantly with no Microsoft
  round trip at all. It creates a real session the exact same way
  real login does, so everything downstream (`/api/session`, admin
  role checks, course CRUD, change requests) works identically. Off
  by default; `/dev-login/<role>` returns 403 unless `DEV_MODE` is
  set. **Never set `DEV_MODE` on anything publicly reachable** — it
  lets anyone log in as any role with zero credentials. Delete this
  once real Azure login works, or at minimum make sure `DEV_MODE`
  never gets set outside a local machine.
- **Bug found and fixed while wiring dev login:** `UserRole` and
  `UserSignOut` used to inherit from `Login`, whose `__init__` eagerly
  builds a full MSAL client — which does a **live call to Microsoft's
  tenant-discovery endpoint** the moment it's constructed. Neither
  class actually uses that client (`UserRole.get_role()` just reads a
  role out of an already-cached dict; `UserSignOut.sign_out()` just
  clears a local session). This meant every role check secretly
  required live Microsoft connectivity and valid Azure config, even
  for a cached session — and would have broken the whole app the
  moment DEV_MODE tried to skip Microsoft, since it wasn't actually
  skippable. Fixed by dropping the unnecessary inheritance on both
  classes.
- **Done:** the login screen now links straight to `/login`
  (Microsoft OAuth) instead of checking a local password. On load,
  `script.js` calls `GET /api/session`; if logged in, it caches
  `{name, email, role}` locally and shows the right screen for that
  role, same as before. `logoutUser()` now redirects to `/logout`
  (clears the real session) instead of just clearing `localStorage`.
  Failed logins redirect back to `/?login_error=...` and show inline
  on the login card instead of a bare error page.
- **Still placeholder config:** `login.py`'s `CLIENT_ID`,
  `CLIENT_SECRET`, `TENANT_ID`, `REDIRECT_URI`, and the post-logout
  redirect URI are all literal placeholder strings. None of this runs
  until whoever owns the Azure AD App Registration fills those in.
- **Role name mismatch risk:** `/api/session` passes through the raw
  Azure AD App Role value for the signed-in user. `script.js` expects
  exactly `"admin"` / `"course_coord"` / `"unit_coord"`
  (case-sensitive). Confirm the App Roles are configured with those
  exact values, or add a mapping in `api_session()` if they end up
  named differently.
- **Resolved — Staff management screen removed** (was here as an open
  question; confirmed identity/roles are Azure AD only, see the
  "Still local-only / not wired" section above for what was deleted).
- **Still separate:** courses/units data (`/api/units`, the course
  dashboard) and the "Request a Change" → `ApprovalReq` wiring are not
  part of this pass — see the gaps above.
