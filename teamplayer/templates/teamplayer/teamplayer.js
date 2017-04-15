{% load staticfiles %}
/*
 * Copyright (c) 2010-2017 marduk enterprises <marduk@python.net>
 *
 */

var TeamPlayer = (function () {
    "use strict";
    return {
        // urls
        urls: {
            home: '{% url "home" %}',
            currently_playing:  '{% url "currently_playing" %}',
            add_to_queue: '{% url "add_to_queue" %}',
            artist_page: '{% url "artist_page" "" %}',
            clear_png: '{% static "images/clear.png" %}',
            web_socket: '{{ websocket_url }}',
            reorder_queue: '{% url "reorder_queue" %}',
            show_stations: '{% url "show_stations" %}',
            show_queue: '{% url "show_queue" %}',
            show_players: '{% url "show_players" %}',
            main_view: '{% url "show_queue" %}',
            player: '{% url "player" %}',
            my_station: '{% url "station_detail" "mine" %}'
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
