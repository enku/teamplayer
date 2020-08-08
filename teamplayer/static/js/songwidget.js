/*
 * Copyright (c) 2010-2020 marduk enterprises <marduk@letterboxes.org>
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
        "use strict";
        var station_id = song_data.station_id;
        var title = song_data.title || 'Unknown';
        var artist = song_data.artist || 'Unknown';
        var dj = song_data.dj || '';
        var artist_image = song_data.artist_image;

        // but actually...
        if (song_data.total_time === 0 && dj === 'DJ Ango') {
            title = 'Station Break';
            artist = '';
        }

        $('.station_' + song_data.station_id + '_song').html(
            '“' + title + '” by ' + artist
        );

        if (station_id !== TP.current_song.station_id) return;

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
        
        if (artist == $('#current_song .song_artist').text()
            && title == $('#current_song .song_title').text()
            && dj == $('#current_song .djname').text())
            return;

        TP.current_song.artist = artist;
        TP.current_song.title = title;
        TP.current_song.dj = dj;

        ttext = (
                'Title: ' 
                + title + '\nArtist: ' + artist + '\nDJ: ' + SongWidget.escapeHTML(dj)
        );

        if (artist_image) {
            // pre-load image
            image.src = artist_image;

            lastfm_str = '<a target="_blank" href="' +
                TP.urls.artist_page + encodeURIComponent(artist) + 
                '"><img src="' + artist_image + '" alt="" /></a>';
        } else {
            lastfm_str = '<img src="' + TP.urls.clear_png + '" alt="" />';
        }

        document.title = (title + ' · ' + artist + ' - TeamPlayer');
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
    },

    clear_queue: function(url) {
        $.ajax({
            url: url,
            type: "POST",
            async: true,
            cache: false,
            success: this.refresh_songlist
        })
    }

    }
})();
