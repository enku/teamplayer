/* websocket handlers */

song_change: function(data) {
    var message = (data.title + ' by ' + data.artist),
        station_name = $('tr[data-station_id="' +
                          data.station_id + '"]').data('name'),
        title = station_name;

    if (data.station_id !== TeamPlayer.current_song.station_id && data.title !== null) {
        if (data.artist_image) {
            Notifier.notify(message, title, data.artist_image);
        } else {
            Notifier.notify(message, title);
        }

    }

    SongWidget.set_songwidget(data);
},

user_stats: function(data) {
    TeamPlayer.update_user_stats(data);
},

station_rename: function(data) {
    TeamPlayer.station_rename(data);
},

station_delete: function(data) {
    TeamPlayer.station_delete(data);
},

station_create: function(data) {
    TeamPlayer.station_create(data);
},

station_stats: function(data) {
    TeamPlayer.station_list_body(data);
},

song_removed: function(data) {
    var entry = $('.song_entry[data-song_id="' + data.id + '"]');
    entry.hide().remove();
    if ($('.song_entry').length === 0) {
        $('#welcome').show();
    }
},

song_added: function(data) {
    var s;

    if (data.station !== TeamPlayer.current_song.station_id) {
        return;
    }
    s = ich.song_template(data);
    TeamPlayer.add_row(s);
},

roster_change: function() {
},

new_connection: function(username) {
    if (username) {
        var text = escape(username) + ' has just joined TeamPlayer.';

        Notifier.info(text, 'New Connection')
    }
},

wall: function (message) {
    Notifier.warning(message, 'DJ Ango');
},

dj_name_change: function (data) {
    if (TeamPlayer.current_song.dj !== '' && 
        TeamPlayer.current_song.dj === data.previous_dj_name) {
        TeamPlayer.current_song.dj = data.dj_name;
        $('#current_song').find('.djname').html(data.dj_name);
    }
}
