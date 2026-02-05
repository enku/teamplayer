#!/usr/bin/env python
"""Broadcast a message to TeamPlayer users"""

import functools
import json
import sys
from typing import Any

import tornado.ioloop
import tornado.websocket
from django.conf import settings as django_settings
from django.core.management.base import BaseCommand

import teamplayer.conf


class Command(BaseCommand):
    help = "Send a wall command over TeamPlayer"

    def handle(self, *args: Any, **options: Any) -> None:
        settings = teamplayer.conf.settings
        message = sys.stdin.read()
        url = f"ws://localhost:{settings.WEBSOCKET_PORT}/ipc"
        ioloop = tornado.ioloop.IOLoop()
        conn = ioloop.run_sync(
            functools.partial(tornado.websocket.websocket_connect, url)
        )
        conn.write_message(
            json.dumps(
                {"type": "wall", "key": django_settings.SECRET_KEY, "data": message}
            )
        )
