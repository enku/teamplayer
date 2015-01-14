/*
 * Copyright (c) 2010-2015 marduk enterprises <marduk@python.net>
 *
 */


/*
 * Code for manipulation the area where the song/dj are displayed
 */
var SongWidget = (function(){
    'use strict';
    return {

    refresh_songlist: function() {
        $.ajax({
            url: TP.urls.show_queue,
            dataType: 'json',
            success: function(data) {
                var $current_list = $('#current_list'),
                    $row,
                    i;

                $current_list.html('');
                if (data.length + $('.song_entry').length > 0) {
                    $('#welcome').hide();
                }
                else {
                    $('#welcome').show();
                }

                for (i in data) {
                    $row = ich.song_template(data[i]);
                    TP.add_row($row, $current_list);
                }
            }
        });
        TP.sortable_songlist();
    },

    get_and_songlist: function(url) {
        // Get url and refresh songlist on success
        $.ajax({url: url,
                async: true,
                cache: true,
                success: this.refresh_songlist,
                });
    },

    escapeHTML: function(s) {
        return(
            s.replace(/&/g,'&amp;').
                replace(/>/g,'&gt;').
                replace(/</g,'&lt;').
                replace(/"/g,'&quot;')
        );
    },

    set_songwidget: function(song_data) {
        $('.station_' + song_data.station_id + '_song').html(
            '“' + song_data.title + '” by ' + song_data.artist
        );

        if (song_data.station_id !== TP.current_song.station_id) return;

        var song_str,
            lastfm_str,
            ttext,
            span,
            image = new Image(60, 60),
            progress = ((song_data.total_time - song_data.remaining_time)
                        / song_data['total_time']
                        * $('#progress_bar').parent().width());

        $('#progress_bar').css({'width': progress});
        $('#progress_bar').stop();
        $('#progress_bar').animate({'width': '100%'}, 
                                   song_data.remaining_time*1000 - 500);
        
        if (song_data.artist == $('#current_song .song_artist').text()
            && song_data.title == $('#current_song .song_title').text()
            && song_data.dj == $('#current_song .djname').text())
            return;

        TP.current_song.artist = song_data['artist'];
        TP.current_song.title = song_data['title'];
        TP.current_song.dj = song_data['dj'];

        ttext = (
                'Title: ' 
                + TP.current_song.title 
                + '\nArtist: ' 
                + TP.current_song.artist + '\nDJ: ' 
                + SongWidget.escapeHTML(TP.current_song.dj)
        );

        if (TP.current_song.artist !== 'Unknown' 
                && song_data['artist_image'] !== '') {
            // pre-load image
            image.src = song_data['artist_image'];

            lastfm_str = '<a target="_blank" href="' +
                TP.urls.artist_page + 
                encodeURIComponent(TP.current_song.artist) + 
                '"><img src="' +
                song_data['artist_image'] + '" alt="" /></a>';}
        else lastfm_str = '<img src="' + TP.urls.clear_png + '" alt="" />';

        document.title = (TP.current_song.title 
                + ' · ' + TP.current_song.artist 
                + ' - TeamPlayer');
        var $current_song = $('#current_song');
        $current_song.fadeOut('fast', function() {
                $current_song.attr('title', ttext);
                $current_song.html(ich.song_widget(
                    TP.current_song
                ));
                $('#lastfm_link').html(lastfm_str);
                $current_song.fadeIn();
        });
        SongWidget.refresh_songlist();
    },

    changesong: function() {
        return $.ajax({
            url: TP.urls.currently_playing,
            async: true,
            cache: false,
            dataType: 'json',
            success: function(data) {
                TP.current_song = data;
                SongWidget.set_songwidget(data);
            }
            //error: changesong
        })
    },

    nextsong: function() {
        $.ajax({
                url: TP.urls.next_song,
                async: true,
                cache: true,
                dataType: 'json',
                success: function(data) {set_songwidget(data); nextsong();},
                })
    }}
})();
