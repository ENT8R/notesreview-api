LINT_FILES = app.py config.py api/ blueprints/ scripts/

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.dev.txt

lint: ty
	ruff check $(LINT_FILES)
	ruff format --diff $(LINT_FILES)

ty:
	ty check $(LINT_FILES) --force-exclude --exclude=scripts/

format:
	ruff check --fix $(LINT_FILES)
	ruff format $(LINT_FILES)

download:
	curl -L -o notes.osn.bz2 https://planet.openstreetmap.org/notes/planet-notes-latest.osn.bz2 && bzip2 -d notes.osn.bz2
