# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ebbinghaus Anywhere (万物皆可艾宾浩斯) is a multi‑user spaced‑repetition flashcard web application built with Django. It supports LaTeX math formulas (via MathJax), chemical equations (via mhchem), and translation lookups via Baidu API. The project is deployed on PythonAnywhere and uses SQLite (default) or MySQL.

## Structure

- `manage.py` – Django command‑line utility.
- `EbbinghausAnywhere/` – Django project settings (`settings.py`, `urls.py`, `wsgi.py`).
- `EAW/` – Main Django app (models, views, templates, static files).
- `api/` – REST API app (DRF, `/api/v1/`): auth (password + WeChat `code2session` binding), review, items, and a superuser‑only full snapshot endpoint used by NAS sync. Token auth via `rest_framework.authtoken`.
- `api/snapshot.py` – snapshot build/validate/restore core shared by the snapshot endpoint and the sync commands.
- `nas-deploy/` – Docker deployment for the NAS replica (Dockerfile, docker-compose.yml, entrypoint.sh, sync.sh). See `docs/DEPLOY_NAS.md`.
- `miniprogram/` – Native WeChat mini‑program client (M3): silent WeChat login + account binding, review loop (YES/NO/RESET), pronunciation playback. Talks to the PA API; backend URL lives in `miniprogram/utils/api.js`. See `miniprogram/README.md`.
- `docs/ARCHITECTURE_PLAN.md` – Architecture plan for the API, NAS sync, and WeChat mini‑program (M1/M2 done; M3 pending).
- `scripts/` – One‑off data tools (not part of the Django app; needs `DEEPSEEK_API_KEY` env var).
- `templates/` – Base HTML templates.
- `static/` and `staticfiles/` – Static assets (CSS, JavaScript, images).
- `.env` – Environment variables (secret key, Baidu API credentials, optional `WECHAT_APPID`/`WECHAT_SECRET`).
- `local_settings.py` – Local database and debug settings (must be created; see below).
- `db.sqlite3` – Default SQLite database.
- `Ellie_user_data_*.xlsx` – Example data export.

## Common Development Tasks

### Environment Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/macOS
   venv\Scripts\activate         # Windows
   ```
2. Install dependencies (see `requirements.txt`; scripts under `scripts/` additionally need `pandas` and `openai`):
   ```bash
   pip install -r requirements.txt
   ```

### Configuration Files

- **`.env`** (already exists) – Must contain:
  ```
  SECRET_KEY=your_django_secret_key
  BAIDU_API_KEY=your_baidu_api_key
  BAIDU_SECRET_KEY=your_baidu_secret_key
  ```
- **`local_settings.py`** (must be created in `EbbinghausAnywhere/`) – Example:
  ```python
  from .settings import BASE_DIR

  DATABASES = {
      "default": {
          "ENGINE": "django.db.backends.sqlite3",
          "NAME": BASE_DIR / "db.sqlite3",
      }
  }
  DEBUG = True
  ```

### Database

- Apply migrations:
  ```bash
  python manage.py migrate
  ```
- Create a superuser:
  ```bash
  python manage.py createsuperuser
  ```

### Running the Development Server

```bash
python manage.py runserver
```

Access the site at http://localhost:8000.

### Frontend Assets

- Bootstrap and MathJax are loaded from CDN in templates.
- Custom static files are in `static/` and collected to `staticfiles/` via `collectstatic`.

### Common Management Commands

- `python manage.py makemigrations` – Create migrations after model changes.
- `python manage.py shell` – Open Django shell.
- `python manage.py collectstatic` – Gather static files for deployment.

### Testing

- Run the test suite:
  ```bash
  python manage.py test              # all 125 tests (EAW + api)
  python manage.py test EAW.tests    # web app only
  python manage.py test api.tests    # REST API only
  ```

## Notes

- The project uses `django-environ` to read secrets from `.env` (see `.env.example` for the template; never commit real keys).
- `EAW/views/` is a package: original `views.py` was split by domain (`accounts`, `items`, `review`, `input`, `data_io`, `translate_api`, `misc`); all names are re-exported from `EAW.views`.
- `EAW/tests/` and `api/tests/` contain the test suites.
- One-off data scripts live in `scripts/` (not part of the Django app); DeepSeek key is read from the `DEEPSEEK_API_KEY` environment variable.
- Baidu translation API is optional; if not configured, translation features will be disabled.
- MathJax/mhchem and Markdown rendering (marked + DOMPurify) are client-side; item content is rendered by `static/js/markdown_render.js` on elements with `data-markdown`.
- REST API (`/api/v1/`) uses DRF Token auth: `POST /api/v1/auth/login/` for a token, then `Authorization: Token <key>`. All registered users have `is_staff=True` — never use DRF's `IsAdminUser` for privileged endpoints; use `api.permissions.IsSuperUser` (the snapshot endpoint already does).
- WeChat binding is **N:1** (`WeChatProfile.user` is a FK): multiple WeChat accounts may bind one main account (family sharing); `openid` is unique so one WeChat belongs to exactly one account (rebinding migrates it).
- Always use `timezone.localdate()` (not `date.today()` / `now().date()`) for "today" — the project runs `USE_TZ=True` with `TIME_ZONE="Asia/Shanghai"`, and UTC dates are one day behind Beijing time after 00:00.
- NAS replica sync: `EAW_ROLE` (`master` default / `replica`) guards `sync_snapshot` and `restore_snapshot` management commands — they refuse to run unless `EAW_ROLE=replica`, so a stale snapshot can never overwrite the master. The replica container also enables WhiteNoise for static files and reads `DATABASE_URL` (e.g. `sqlite:////data/db.sqlite3`); the master (PA) is unaffected by all of these.
- The `EAW` app contains the core flashcard logic, models, and views.
- Refer to the `README.md` for detailed user instructions and deployment guidelines.