# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ebbinghaus Anywhere (万物皆可艾宾浩斯) is a multi‑user spaced‑repetition flashcard web application built with Django. It supports LaTeX math formulas (via MathJax), chemical equations (via mhchem), and translation lookups via Baidu API. The project is deployed on PythonAnywhere and uses SQLite (default) or MySQL.

## Structure

- `manage.py` – Django command‑line utility.
- `EbbinghausAnywhere/` – Django project settings (`settings.py`, `urls.py`, `wsgi.py`).
- `EAW/` – Main Django app (models, views, templates, static files).
- `templates/` – Base HTML templates.
- `static/` and `staticfiles/` – Static assets (CSS, JavaScript, images).
- `.env` – Environment variables (secret key, Baidu API credentials).
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
  python manage.py test
  ```

## Notes

- The project uses `django-environ` to read secrets from `.env` (see `.env.example` for the template; never commit real keys).
- `EAW/views/` is a package: original `views.py` was split by domain (`accounts`, `items`, `review`, `input`, `data_io`, `translate_api`, `misc`); all names are re-exported from `EAW.views`.
- `EAW/tests/` contains the test suite (`python manage.py test EAW.tests`).
- One-off data scripts live in `scripts/` (not part of the Django app); DeepSeek key is read from the `DEEPSEEK_API_KEY` environment variable.
- Baidu translation API is optional; if not configured, translation features will be disabled.
- MathJax/mhchem and Markdown rendering (marked + DOMPurify) are client-side; item content is rendered by `static/js/markdown_render.js` on elements with `data-markdown`.
- The `EAW` app contains the core flashcard logic, models, and views.
- Refer to the `README.md` for detailed user instructions and deployment guidelines.