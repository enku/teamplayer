PYTHON := python3.8
NAME := $(shell $(PYTHON) setup.py --name)
VERSION = $(shell $(PYTHON) setup.py --version)

SDIST = dist/$(NAME)-$(VERSION).tar.gz
WHEEL = dist/$(NAME)-$(VERSION)-py3-none-any.whl
SOURCE = setup.py MANIFEST.in $(shell find teamplayer -type f -print)

export PATH := $(CURDIR)/bin:$(PATH)

export DJANGO_DEBUG

all: $(SDIST) $(WHEEL)

.venv: setup.py
	$(PYTHON) -m venv .
	$(PYTHON) -m pip install black coverage wheel Whoosh -e .
	touch $@

venv: .venv

$(SDIST): $(SOURCE) .venv
	$(PYTHON) setup.py sdist

sdist: $(SDIST)

$(WHEEL): $(SOURCE) .venv
	$(PYTHON) setup.py bdist_wheel

test: venv
	black --check teamplayer
	rm -rf project
	django-admin.py startproject project
	cp tools/settings.py project/project/settings.py
	cp tools/urls.py project/project/urls.py
	coverage erase
	coverage run --source=teamplayer project/manage.py test --failfast teamplayer
	coverage report
	coverage html

docker:
	docker-compose up

clean:
	rm -rf .coverage .venv bin build dist htmlcov lib lib64 project share
	find . -type f -name '*.py[co]' -delete


.PHONY: all clean docker sdist test venv wheel
