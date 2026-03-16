# consensio
Web application for majority judgment voting

## How to deploy

Copy consensio forlder into `/var/www`

Modify some settings

### Script `settings.py`

Complete line `load_dotenv` by setting the path to your `.env` file

Set `DEBUG` variable to `False`

Complete list `ALLOWED_HOST` by teh hots URL you want to allow

### Create virtual environment

`python3 -m venv .venv`

### Create a superuser

`python manage.py createsuperuser`


