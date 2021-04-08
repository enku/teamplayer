PYTHON := python3.8
NAME := $(shell $(PYTHON) setup.py --name)
VERSION = $(shell $(PYTHON) setup.py --version)

SDIST = dist/$(NAME)-$(VERSION).tar.gz
WHEEL = dist/$(NAME)-$(VERSION)-py3-none-any.whl
SOURCE = setup.py MANIFEST.in $(shell find teamplayer -type f -print)
VENV := .venv/dirstate

export PATH := $(CURDIR)/.venv/bin:$(PATH)
export DJANGO_DEBUG

all: $(SDIST) $(WHEEL)

$(VENV): setup.py teamplayer/tests/requirements.txt
	$(PYTHON) -m venv .venv
	$(PYTHON) -m pip install --upgrade pip wheel -r teamplayer/tests/requirements.txt -e .
	touch $@

.PHONY: venv
venv: $(VENV)

$(SDIST): $(SOURCE) $(VENV)
	$(PYTHON) setup.py sdist

sdist: $(SDIST)

$(WHEEL): $(SOURCE) $(VENV)
	$(PYTHON) setup.py bdist_wheel

.PHONY: test
test .coverage: $(VENV)
	black --check teamplayer
	rm -rf project
	django-admin.py startproject project
	cp tools/settings.py project/project/settings.py
	cp tools/urls.py project/project/urls.py
	coverage erase
	coverage run --source=teamplayer project/manage.py test -v2 --failfast teamplayer
	coverage report

.PHONY: coverage-report
coverage-report: .coverage
	coverage html
	$(PYTHON) -m webbrowser -t file://$(CURDIR)/htmlcov/index.html

.PHONY: docker
docker:
	docker-compose -f docker-compose.yml -f docker-compose-dev.yml up

.PHONY: shell
shell: $(VENV)
	source .venv/bin/activate && $(SHELL)

.PHONY: clean
clean:
	rm -rf .coverage .venv build dist htmlcov project
