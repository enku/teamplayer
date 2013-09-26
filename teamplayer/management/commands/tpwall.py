#!/usr/bin/env python
"""Broadcast a message to TeamPlayer users"""
import functools
import json
import sys

from django.core.management.base import BaseCommand

import tornado.ioloop
import tornado.websocket

import teamplayer.conf


class Command(BaseCommand):
    help = 'Send a wall command over TeamPlayer'
    def handle(self, *args, **options):
        settings = teamplayer.conf.settings
        message = sys.stdin.read()
        url = 'ws://localhost:%s/ipc' % settings.IPC_PORT
        ioloop = tornado.ioloop.IOLoop()
        conn = ioloop.run_sync(functools.partial(
            tornado.websocket.websocket_connect, url))
        conn.write_message(json.dumps(
            {
                'type': 'wall',
                'data': message,
            }
        ))
