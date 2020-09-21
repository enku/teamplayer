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


if [ -z "$DJANGO_SECRET_KEY" ]; then
    key=/opt/teamplayer/.key
    if [ ! -e $key ]; then
        touch $key
        chmod 0400 $key
        python3 -c 'from django.core.management import utils; print(utils.get_random_secret_key())' >> $key
    fi
    DJANGO_SECRET_KEY=`cat $key`
fi

export DJANGO_SECRET_KEY

# migrate the data
if ! python3 $MANAGE_PY migrate; then
    echo "Migration failed. Will try again later" > /dev/stderr
    sleep 10
    python3 $MANAGE_PY migrate
fi
python3 $MANAGE_PY spindoctor &

if [ -n "${TEAMPLAYER_WALK}" ] ; then
    python3 $MANAGE_PY tplibrarywalk "${TEAMPLAYER_WALK}" &
fi

if [ "${DJANGO_DEBUG}" -ne 0 ] ; then
    python3 $MANAGE_PY runserver -v2 0.0.0.0:9000
else
    gunicorn -w 4 --bind 0.0.0.0:9000 project.wsgi
fi
