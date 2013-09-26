/* websocket handlers */

song_change: function(data) {
    var message = ('<span class="song_title">' +
                   data.title +
                   '</span>' +
                   ' by ' +
                    data.artist),
        station_name = $('tr[data-station_id="' +
                          data.station_id + '"]').data('name'),
        title = ('<a class="notify_title station_name station_' 
                 + data.station_id + '_name" ' +
                 'onclick="return TeamPlayer.change_station(this.href)" ' +
                 'href="/station/' + data.station_id  +
                 '/">' +
                 station_name +
                 '</a>');

    if (data.station_id !== TeamPlayer.current_song.station_id) {
        $.pnotify({
            title: title,
            text: message,
            width: "150px",
            icon: false,
            shadow: false,
            sticker: false
        });
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
        $.pnotify({
            title: 'New Connection',
            text: escape(username) + ' has just joined <span class="brand">TeamPlayer</span>.' ,
            text_escape: false,
            width: "150px",
            shadow: false,
            sticker: false,
            nonblock: true
        });
    }
},

wall: function (message) {
    $.pnotify({
        title: '<span class="warning"><i class="icon-warning-sign"></i> DJ Ango</span>',
        text: message,
        text_escape: true,
        icon: false,
        shadow: false,
        sticker: false,
        hide: false
    });
},

dj_name_change: function (data) {
    if (TeamPlayer.current_song.dj !== '' && 
        TeamPlayer.current_song.dj === data.previous_dj_name) {
        TeamPlayer.current_song.dj = data.dj_name;
        $('#current_song').find('.djname').html(data.dj_name);
    }
}
