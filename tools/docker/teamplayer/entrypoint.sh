#!/bin/sh
set -e

PATH=/opt/teamplayer/.local/bin:"${PATH}"
DJANGO_SETTINGS_MODULE=project.settings ; export DJANGO_SETTINGS_MODULE
MANAGE_PY=/opt/teamplayer/manage.py

# migrate the data
sleep 3
python3 $MANAGE_PY migrate
python3 $MANAGE_PY spindoctor &
gunicorn -w 4 --bind 0.0.0.0:9000 project.wsgi
