#!/bin/sh
set -e

PATH=/opt/teamplayer/.local/bin:"${PATH}"
DJANGO_SETTINGS_MODULE=project.settings ; export DJANGO_SETTINGS_MODULE
MANAGE_PY=/opt/teamplayer/manage.py
DJANGO_DEBUG=${DJANGO_DEBUG:-0}

if [ "${DJANGO_DEBUG}" -ne 0 ] ; then
    echo "Running in debug mode"
    PYTHONPATH=/usr/src/teamplayer
    export PYTHONPATH
fi

# migrate the data
sleep 3
python3 $MANAGE_PY migrate
python3 $MANAGE_PY spindoctor &

if [ -n "${TEAMPLAYER_WALK}" ] ; then
    python3 $MANAGE_PY tplibrarywalk "${TEAMPLAYER_WALK}" &
fi

if [ "${DJANGO_DEBUG}" -ne 0 ] ; then
    python3 $MANAGE_PY runserver -v2 0.0.0.0:9000
else
    gunicorn -w 4 --bind 0.0.0.0:9000 project.wsgi
fi
