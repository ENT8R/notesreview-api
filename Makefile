LINT_FILES = app.py api/ scripts/

install:
	pip install -r requirements.txt  

lint:
	flake8 --count --extend-ignore=E501 --show-source --statistics $(LINT_FILES)

# Enable black with "black --check --skip-string-normalization $(LINT_FILES)" after code cleanup
format:
	isort --check-only $(LINT_FILES)
