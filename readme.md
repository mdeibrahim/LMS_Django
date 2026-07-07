#  Teaching Platform

A Django-based  learning platform where a lesson page can include clickable highlighted text that opens multimedia content (text, image, audio, video, YouTube) in a modal.

## Features

- Category -> SubCategory -> Subject content hierarchy
-  lesson body with clickable highlight links
- Multimedia content types: text, image, audio, video, YouTube
- Accordion-based sidebar sections per subject
- Frontend subject editor for:
- Rich text editing (bold/italic/underline)
- Linking selected text to media items
- Creating/updating/deleting media items and accordion sections
- Django admin with `django-unfold` UI and custom dashboard
- Demo seed command for sample data

## Tech Stack

- Python 3
- Django 6
- SQLite
- django-unfold (admin UI)
- Vanilla JavaScript + Django templates

## Project Structure

```text
content/
  models.py
  views.py
  admin.py
  dashboard.py
  management/commands/seed_demo.py
teaching_platform/
  settings.py
  urls.py
  unfold_config.py
templates/content/
  home.html
  category_detail.html
  subcategory_detail.html
  lesson_detail.html
  subject_editor.html
static/js/
  subject.js
  editor.js
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run migrations.
4. Create an admin user.
5. (Optional) Seed demo content.
6. Start the server.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo   # optional demo content
python manage.py runserver
```

Open:

- App: `http://127.0.0.1:8000/`
- Admin dashboard: `http://127.0.0.1:8000/admin/dashboard/`
- Admin panel: `http://127.0.0.1:8000/admin/`

## Main URLs

- `/` -> home (all categories)
- `/category/<cat_slug>/` -> subcategories
- `/category/<cat_slug>/<subcat_slug>/` -> subjects
- `/courses/<course_slug>/` -> course modules page with collapsible lessons and MCQ
- `/courses/<course_slug>/modules/<module_slug>/lessons/<lesson_slug>/` -> lesson details page
- `/courses/<course_slug>/modules/<module_slug>/lessons/<lesson_slug>/quizzes/<quiz_id>/` -> lesson MCQ page

## API Endpoints (AJAX)

- `GET /api/content/<content_id>/` ->  content payload
- `GET /api/subject/<subject_id>/` -> full subject JSON
- `POST /api/subject/<subject_id>/save/` -> save subject title/body
- `POST /api/subject/<subject_id>/ic/create/` -> create  content
- `POST /api/ic/<ic_id>/update/` -> update content
- `POST|DELETE /api/ic/<ic_id>/delete/` -> delete content
- `POST /api/subject/<subject_id>/accordion/create/` -> create accordion section
- `POST /api/accordion/<section_id>/update/` -> update accordion section
- `POST|DELETE /api/accordion/<section_id>/delete/` -> delete accordion section

## Content Authoring Note

`Subject.body_content` stores HTML. links are embedded like:

```html
<span class="highlight-link" data-content-id="12">Click this term</span>
```

When users click the highlight in the subject page, the platform fetches media details and opens the related modal content.

## Admin Dashboard

The custom admin dashboard (`/admin/dashboard/`) includes:

- content totals (categories, subcategories, subjects, sections, media items)
- health metrics (coverage, empty branches, average media per subject)
- recent updates and content distribution by type

## Demo Data

Run:

```bash
python manage.py seed_demo
```

This creates a sample journalism category tree, one subject, media entries, and accordion sections.

## Media & Static

- Uploaded media is stored in `media/`
- Static assets are in `static/`
- In development, media is served via Django URL config

## Notes

- `DEBUG=True` and `ALLOWED_HOSTS=['*']` are currently set for development.
- Update secret key, debug, and host settings before production deployment.
