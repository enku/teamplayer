FROM ubuntu

LABEL Description "TeamPlayer wsgi service"

MAINTAINER Albert Hopkins <marduk@letterboxes.org>

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    mercurial \
    mpd \
    python3 \
    python3-dev \
    python3-pip \
    && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -c "Teamplayer Server" -U -d /opt/teamplayer -m teamplayer

USER teamplayer

RUN pip3 install -U --user pip setuptools && \
    /opt/teamplayer/.local/bin/pip install --user --no-cache \
        git+https://github.com/enku/teamplayer/ \
        gunicorn \
        psycopg2 \
        whoosh && \
    /opt/teamplayer/.local/bin/django-admin startproject project /opt/teamplayer && \
    mkdir /opt/teamplayer/songs \
          /opt/teamplayer/media \
	  /opt/teamplayer/library \
	  /opt/teamplayer/mpd

COPY settings.py urls.py /opt/teamplayer/project/

RUN python3 /opt/teamplayer/manage.py collectstatic --noinput

COPY entrypoint.sh /opt/teamplayer

WORKDIR /opt/teamplayer

VOLUME /opt/teamplayer/static

EXPOSE 8100

CMD ["/opt/teamplayer/entrypoint.sh"]
