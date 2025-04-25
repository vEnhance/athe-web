## Quick start

1. Install Python, Git, and [Hatch](https://hatch.pypa.io/1.9/)
2. Clone this repository and cd to it.
3. `hatch run dev:migrate`
4. `hatch run dev:createsuperuser` and create an admin username and password
5. Maybe try `hatch run python manage.py loaddata fixtures/example.json`
   - This command will probably break later once we add more fields
6. `hatch run dev:runserver`
7. See if `https://127.0.0.1:8000/` shows a course listing now
8. Go to `https://127.0.0.1:8000/admin/` and login with the admin user you made.
9. Edit Semesters and Courses as you see fit.
10. See if the changes are reflect when you go back to the main page.
