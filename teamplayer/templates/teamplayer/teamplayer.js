{% load staticfiles %}
/*
 * Copyright (c) 2010-2015 marduk enterprises <marduk@python.net>
 *
 */

var TeamPlayer = (function () {
    "use strict";
    return {
        // urls
        urls: {
            home: '{% url "teamplayer.views.home" %}',
            currently_playing:  '{% url "teamplayer.views.currently_playing" %}',
            add_to_queue: '{% url "teamplayer.views.add_to_queue" %}',
            artist_page: '{% url "teamplayer.views.artist_page" "" %}',
            clear_png: '{% static "images/clear.png" %}',
            web_socket: '{{ websocket_url }}',
            reorder_queue: '{% url "teamplayer.views.reorder_queue" %}',
            show_stations: '{% url "teamplayer.views.show_stations" %}',
            show_queue: '{% url "teamplayer.views.show_queue" %}',
            show_players: '{% url "teamplayer.views.show_players" %}',
            main_view: '{% url "teamplayer.views.show_queue" %}',
            player: '{% url "teamplayer.views.player" %}',
            my_station: '{% url "teamplayer.views.station_detail" "mine" %}'
        },

        // current song
        current_song: {
            artist: 'Unknown',
            title: 'Unknown',
            dj: '',
            station_id: 1,
            station_name: 'Main Station'
        },

        // "user stats"
        user_stats: {
            stations: 0,
            active_queues: 0,
            songs: 0,
            users: 0
        },

        muted: false,
        username: '{{ username|escapejs }}',

        {% include "teamplayer/functions.js" %}

        websocket_handlers: {
            {% include "teamplayer/websocket_handlers.js" %}
        }
};})();

var TP = TeamPlayer;

$(document).ready({% include "teamplayer/main.js" %});
