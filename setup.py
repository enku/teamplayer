#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='TeamPlayer',
    version=__import__('teamplayer').version_string(show_revision=False),
    description='A Democratic Internet Radio Station',
    author='Albert Hopkins',
    author_email='marduk@python.net',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Django>=1.8,<1.11',
        'django-haystack>=2.4,<2.5',
        'mutagen>=1.29,<1.30',
        'pylast>=1.2,<1.3',
        'python-mpd2',
        'tornado',
        'djangorestframework>=3.5,<3.6'
    ],
)
