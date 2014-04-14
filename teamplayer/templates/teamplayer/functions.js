/* functions belonging to the TeamPlayer namespace */
/* callback to show the dialog to change the dj name */
show_dj_dialog: function (e) {
    $('#dj_name_link').hide();
    $('#change_dj_name').fadeIn('slow');
    e.preventDefault();
},


/* change the dj name */
change_dj_name: function (data) {
    var dj_name;

    if (data) {
        alert(data);
        return false;
    }

    dj_name = $('#dj_name').val();
    if (dj_name.length === 0) {
        dj_name = 'Anonymous';
    }
    $('#dj_name_link').text(dj_name);
    $('#change_dj_name').hide();
    $('#dj_name_link').show();
    return true;
},


// change the station without a document load
change_station: function (url) {
    var $main_view = $('#main_view'),
        orig_class = 'station_' + TeamPlayer.current_song.station_id + '_name',
        new_class;

    $('#station_static')[0].play();
    $main_view.spin();
    $.ajax({
        dataType: 'json',
        url: url,
        success: function (station) {
            TeamPlayer.play(station.stream);
            TeamPlayer.current_song = station.current_song;
            SongWidget.set_songwidget(station.current_song);
            SongWidget.refresh_songlist();
            MainView.show('queue');
            history.pushState(null, null, station.url);
            $('.current_station').text(station.name);
            new_class = 'station_' + station.id + '_name';
            $('.current_station.' + orig_class).removeClass(orig_class).addClass(
                new_class);
        },
        complete: function () {
            $main_view.spin(false); 
            $('#station_static')[0].pause();
            $('body').css('cursor', 'default')
        }
    })
    return false;
},


change_station_prev: function () {
    return TeamPlayer.change_station(
            '{% url "teamplayer.views.previous_station" %}');
},


change_station_next: function () {
    return TeamPlayer.change_station(
            '{% url "teamplayer.views.next_station" %}');
},


change_station_home: function() {
    return TeamPlayer.change_station(
            '{% url "station" home %}');
},


add_row: function ($row, $target) {
    if ($target === undefined) {
        $target = $('#current_list');
    }

    $target.append($row);

    // insert drag grips in the first spacer when hovering over the entry
    $row.hover(
        function () {
            $(this).find('.song_spacer:first').html('&#8801;');
        },
        function () {
            $(this).find('.song_spacer:first').html('');
        }
    );
    $row.disableSelection();
    return $row;
},


/* Make (sure) the song list sortable */
sortable_songlist: function () {
    var $list = $('#current_list');

    $list.sortable({
        items: "tr",
        axis: "y",
        cursor: "move",
        handle: ".song_spacer",
        update: function () {
            var data = [];
            $(this).find(".song_entry").each(function () {
                data.push($(this).data("song_id"));
            });
            $.post(TeamPlayer.urls.reorder_queue, data.join(","));
        }
    });
    /* I'm not sure that I need this.  I think JB added it */
    //$list.disableSelection();
},


/* toggle the menu display */
toggle_controls: function () {
    $('#controls').slideToggle('fast');
},


/* 
 * remove song_id from the queue. Show the welcome text if there is nothing
 * left in the queue or upload list. 
 */
remove_from_queue: function (song_id) {
    $.ajax({
        url: '{% url "teamplayer.views.show_queue" %}' + song_id,
        type: 'DELETE',
        success: function () {
            $('tr[data-song_id="' + song_id + '"]').remove();
            if ($('.song_entry').length === 0) {
                $('#welcome').show();
            }
        }
    });
},

update_user_stats: function (stats) {
    var text = ich.user_stats(stats);

    stats = stats || TeamPlayer.user_stats;
    TeamPlayer.user_stats = stats;

    $('#queue_tray').html(text);
},

station_rename: function (data) {
    var station_id = data[0],
        new_name = data[1];

    $('.station_' + station_id + '_name').text(new_name);

    if (TeamPlayer.current_song.station_id === station_id) {
        TeamPlayer.current_song.station_name = new_name;
    }
},

station_delete: function (station_id) {
    var str = 'tr.station[data-station_id="' + station_id + '"]';
    $(str).remove();

    // redirect to home if current station was deleted
    if (TeamPlayer.current_song.station_id === station_id) {
        TeamPlayer.change_station(TeamPlayer.urls.home);
    }
},

station_create: function (station) {
    var html = ich.station_row(station);
    $('#station_list_body').append(html);
    
    if (station.creator === TeamPlayer.username) {
        TeamPlayer.change_station(station.url);
        TeamPlayer.station_tray_body();
        return;
    }

    if (station.id !== TeamPlayer.current_song.station_id) {
        $.pnotify({
            title: 'New Station',
            text: '<span class="station_name"><a href="' + station.url + '">' + station.name + '</a>',
            width: "150px",
            shadow: false,
            sticker: false,
            nonblock: true
        });
    }
},

station_list_body: function () {
    var html = '',
        i,
        station;

    $.ajax({
        url: '{% url "teamplayer.views.show_stations" %}',
        dataType: 'json',
        success: function (station_info) {
            for (i = 0; i < station_info.length; i += 1) {
                station = station_info[i];

                html = html + ich.station_row(station).get()[0].outerHTML;
            }

            $('#station_list_body').html(html);
        }
    });
    
},

/* big, horrible monstrosity */
station_tray_body: function () {
    var html = '',
        $tray = $('#stations_tray');

    $.ajax({
        url: TeamPlayer.urls.my_station,
        dataType: 'json',
        success: function (station) {
            html = ich.station_tray({
                station_id: station.id,
                name: station.name,
                edit_station_url: '{% url "teamplayer.views.edit_station" %}',
                username: TeamPlayer.username,
                create_station_url: '{% url "teamplayer.views.create_station" %}'
            });
            $tray.html(html);

            $('#station_change_form').ajaxForm(function(message) {
                if (message) {
                    alert(message);
                }
                else {
                    $('#station_edit_dialog').dialog('close', 'explode');
                    TeamPlayer.station_tray_body();
                }
            });

            $('#station_edit_dialog').dialog(
            {
                modal: true,
                autoOpen: false
            });
            $('#open_edit_dialog').click(function() {
                $('#station_edit_dialog').dialog('open');
            });
        },
        error: function () {
            html = ich.station_tray({
                edit_station_url: '{% url "teamplayer.views.edit_station" %}',
                username: TeamPlayer.username,
                create_station_url: '{% url "teamplayer.views.create_station" %}'
            });
            $tray.html(html);
            
            $('#station_create_dialog').dialog({
                modal: true,
                autoOpen: false
            });

            $('#open_create_dialog').click(function () {
                $('#station_create_dialog').dialog('open');
            });

            $('#station_create_form').ajaxForm(function (message) {
                if (message) {
                    alert(message);
                }
                else {
                    $('#station_create_dialog').dialog('close');
                    $('body').css('cursor', 'wait')
                }
            });
        },
        complete: function () {
            $('#station_list_ok').ajaxForm(function() { 
                MainView.show('queue');
            });
        }
    });
},

websocket_connect: function () {
    var socket = new ReconnectingWebSocket(this.urls.web_socket);

    socket.onmessage = function (message) {
        message = JSON.parse(message.data);

        if (TeamPlayer.websocket_handlers.hasOwnProperty(message.type)) {
            TeamPlayer.websocket_handlers[message.type](message.data);
        }
    };
},
