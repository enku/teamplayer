FROM python:3.8

COPY setup.py MANIFEST.in README.rst AUTHORS /usr/src/teamplayer/
COPY teamplayer/ /usr/src/teamplayer/teamplayer/
RUN pip install --no-cache-dir /usr/src/teamplayer gunicorn psycopg2 whoosh &&  rm -rf /usr/src/teamplayer

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends mpd && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/teamplayer/songs /opt/teamplayer/media /opt/teamplayer/library /opt/teamplayer/mpd
RUN django-admin startproject project /opt/teamplayer
COPY tools/docker/settings.py tools/docker/urls.py /opt/teamplayer/project/
COPY tools/docker/entrypoint.sh /opt/teamplayer
RUN python3 /opt/teamplayer/manage.py collectstatic --noinput

WORKDIR /opt/teamplayer
VOLUME /opt/teamplayer/static
CMD ["/opt/teamplayer/entrypoint.sh"]
