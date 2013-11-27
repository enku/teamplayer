#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from setuptools import setup


def get_package_data(package):
    walk = [(dirpath.replace(package + os.sep, '', 1), filenames) for dirpath,
            dirnames, filenames in os.walk(package)
            if not os.path.exists(os.path.join(dirpath, '__init__'))]

    filepaths = []
    for base, filenames in walk:
        filepaths.extend([os.path.join(base, filename)
                         for filename in filenames])

    return filepaths

setup(
    name='TeamPlayer',
    version=__import__('teamplayer').version_string(show_revision=False),
    description='A Democratic Internet Radio Station',
    author='Albert Hopkins',
    author_email='marduk@python.net',
    packages=['teamplayer', 'tp_library'],
    package_data={'teamplayer': get_package_data('teamplayer'),
                  'tp_library': get_package_data('tp_library')},
    install_requires=[
        'Django>=1.5.5,<1.7',
        'django-haystack==2.1.0',
        'mutagen',
        'python-mpd',
        'tornado',
        'djangorestframework==2.3.8'
    ],
    setup_requires=[
        'mock',
    ],
)

k
