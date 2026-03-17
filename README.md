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

### Move static files

Once virtual environment is activated, run :
`python manage.py collectstatic`

### Create a superuser

`python manage.py createsuperuser`


## Changelog

### 0.2.0

 - Add elector groups
 - Add CSV import of electors
 - Add CSV import of candidates
 - Add interactive toggling fo conflicts of interest
 - Improve electors/candidates management of existing election
 - Simplify ex-aequo managment : only display, no resolution

### 0.1.0

Initial version

