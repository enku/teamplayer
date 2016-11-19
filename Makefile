PYTHON := python3.4
VERSION = $(shell python -c 'import teamplayer; print(teamplayer.version_string(show_revision=False))')

SDIST = dist/TeamPlayer-$(VERSION).tar.gz
WHEEL = dist/TeamPlayer-$(VERSION)-py3-none-any.whl
SOURCE = setup.py teamplayer tp_library MANIFEST.in

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
	docker-compose -f tools/docker/docker-compose.yml up

clean:
	rm -rf .tox build dist
	find . -type f -name '*.py[co]' -delete


.PHONY: all clean docker sdist test wheel
