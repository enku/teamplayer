#!/usr/bin/env python
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
        'Django>=1.7,<1.8',
        'django-haystack>=2.1,<2.2',
        'mutagen>=1.26,<1.27',
        'python-mpd2',
        'tornado',
        'djangorestframework>=2.3.10,<2.4'
    ],
    setup_requires=[
        'mock',
    ],
)
