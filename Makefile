NAME := $(shell pdm show --name)
VERSION = $(shell pdm show --version)

SDIST = dist/$(NAME)-$(VERSION).tar.gz
WHEEL = dist/$(NAME)-$(VERSION)-py3-none-any.whl
SOURCE = setup.py MANIFEST.in $(shell find teamplayer -type f -print)

export DJANGO_DEBUG

all: $(SDIST) $(WHEEL)

$(SDIST): $(SOURCE)
	pdm build --no-wheel

sdist: $(SDIST)

$(WHEEL): $(SOURCE)
	pdm build --no-sdist

.PHONY: test
test .coverage:
	black --check teamplayer
	rm -rf project
	django-admin startproject project
	cp tools/settings.py project/project/settings.py
	cp tools/urls.py project/project/urls.py
	coverage erase
	coverage run --source=teamplayer project/manage.py test -v2 --failfast tests
	coverage report

.PHONY: coverage-report
coverage-report: .coverage
	coverage html
	python -m webbrowser -t file://$(CURDIR)/htmlcov/index.html

mypy:
	pdm run mypy
.PHONY: mypy

.PHONY: docker
docker:
	docker-compose -f docker-compose.yml -f docker-compose-dev.yml up

.PHONY: shell
shell:
	pdm run $(SHELL)

.PHONY: clean
clean:
	rm -rf .coverage .venv build dist htmlcov project __pypackages__	
