## Quick start

1. Install Python, Git, and [uv](https://docs.astral.sh/uv/)
2. Clone this repository and cd to it.
3. `make install` (or `uv sync --all-extras`)
4. `make migrate` (or `uv run python manage.py migrate`)
5. `make createsuperuser` (or `uv run python manage.py createsuperuser`) and create an admin username and password
6. Maybe try `uv run python manage.py loaddata fixtures/example.json`
   - This command will probably break later once we add more fields
7. `make runserver` (or `uv run python manage.py runserver_plus`)
8. See if `http://127.0.0.1:8000/` shows a course listing now
9. Go to `http://127.0.0.1:8000/admin/` and login with the admin user you made.
10. Edit Semesters and Courses as you see fit.
11. See if the changes are reflected when you go back to the main page.

## Common commands

Run `make help` to see all available commands, or use `uv run python manage.py <command>` directly.
