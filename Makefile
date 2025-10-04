LINT_FILES = app.py config.py api/ blueprints/ scripts/

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.dev.txt

lint:
	flake8 --count --extend-ignore=E501 --show-source --statistics $(LINT_FILES)

format:
	isort --check-only $(LINT_FILES)
	black --check --diff --skip-string-normalization $(LINT_FILES)

download:
	curl -o notes.osn.bz2 https://ftp5.gwdg.de/pub/misc/openstreetmap/planet.openstreetmap.org/notes/planet-notes-latest.osn.bz2 && bzip2 -d notes.osn.bz2
