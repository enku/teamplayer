#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='TeamPlayer',
    version=__import__('teamplayer').version_string(show_revision=False),
    description='A Democratic Internet Radio Station',
    author='Albert Hopkins',
    author_email='marduk@letterboxes.org',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Django>=1.10,<1.12',
        'django-haystack>=2.8,<2.9',
        'djangorestframework>=3.5,<3.6',
        'mutagen>=1.29,<1.30',
        'pylast>=1.6,<1.7',
        'python-mpd2',
        'tornado',
    ],
    entry_points={
        'teamplayer.autofill_strategy': [
            'contiguous = teamplayer.lib.autofill:auto_fill_contiguous',
            'mood = teamplayer.lib.autofill:auto_fill_mood',
            'random = teamplayer.lib.autofill:auto_fill_random',
        ],
    },
)
