## Quick start

1.  Install Python, Git, and [uv](https://docs.astral.sh/uv/)
1.  Clone this repository and cd to it.
1.  `make install` (or `uv sync`)
1.  `make migrate` (or `uv run python manage.py migrate`)
1.  Use `uv run python manage.py createsuperuser` and create an admin username and password
1.  Maybe try `uv run python manage.py loaddata fixtures/example.json`
    - This command will probably break later once we add more fields
1.  `make runserver` (or `uv run python manage.py runserver_plus`)
1.  See if `http://127.0.0.1:8000/` shows a course listing now
1.  Go to `http://127.0.0.1:8000/admin/` and login with the admin user you made.
1.  Edit Semesters and Courses as you see fit.
1.  See if the changes are reflected when you go back to the main page.

## Common commands

Run `make help` to see all available commands, or use `uv run python manage.py <command>` directly.
