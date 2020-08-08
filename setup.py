#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name="TeamPlayer",
    version=__import__("teamplayer").version_string(show_revision=False),
    description="A Democratic Internet Radio Station",
    author="Albert Hopkins",
    author_email="marduk@letterboxes.org",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Django>=2.2.8,<3.1",
        "django-haystack>=3.0b2,<3.1",
        "djangorestframework>=3.11.1,<3.12",
        "mutagen>=1.29,<1.30",
        "pylast>=1.6,<1.7",
        "python-mpd2",
        "tornado",
    ],
    entry_points={
        "teamplayer.autofill_strategy": [
            "contiguous = teamplayer.lib.autofill:auto_fill_contiguous",
            "mood = teamplayer.lib.autofill:auto_fill_mood",
            "random = teamplayer.lib.autofill:auto_fill_random",
        ],
    },
)
