PYTHON := python3.4
NAME := $(shell $(PYTHON) setup.py --name)
VERSION = $(shell $(PYTHON) setup.py --version)

SDIST = dist/$(NAME)-$(VERSION).tar.gz
WHEEL = dist/$(NAME)-$(VERSION)-py3-none-any.whl
SOURCE = setup.py MANIFEST.in $(shell find teamplayer -type f -print)

export DJANGO_DEBUG

all: $(SDIST) $(WHEEL)

$(SDIST): $(SOURCE)
	$(PYTHON) setup.py sdist

sdist: $(SDIST)

$(WHEEL): $(SOURCE)
	$(PYTHON) setup.py bdist_wheel

test:
	tox -e py34-django10

docker:
	docker-compose -p $(NAME) -f tools/docker/docker-compose.yml build
	docker-compose -p $(NAME) -f tools/docker/docker-compose.yml up

clean:
	rm -rf .tox build dist
	find . -type f -name '*.py[co]' -delete


.PHONY: all clean docker sdist test wheel
